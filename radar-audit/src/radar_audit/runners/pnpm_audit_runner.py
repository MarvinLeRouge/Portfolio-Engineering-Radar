from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "moderate": "MEDIUM",
    "low": "LOW",
    "info": "LOW",
}

# Priority order when a target directory somehow carries more than one
# lockfile: npm first (most universal), then pnpm, then yarn. This dict is
# also the source of truth for which lockfile filenames are recognized at
# all -- _detect_lockfile walks its keys in this order.
_LOCKFILE_COMMANDS: dict[str, list[str]] = {
    "package-lock.json": ["npm", "audit", "--json"],
    "pnpm-lock.yaml": ["pnpm", "audit", "--json"],
    # yarn is dispatched through npx (like JscpdRunner's jscpd) rather than a
    # bare `yarn` binary, since yarn classic is not guaranteed to be globally
    # installed the way npm (ships with Node) and pnpm (assumed present,
    # matching this runner's pre-existing pnpm-audit convention) are.
    "yarn.lock": ["npx", "--package=yarn", "--", "yarn", "audit", "--json"],
}

_PARSER_NAMES: dict[str, str] = {
    "package-lock.json": "_parse_npm_audit",
    "pnpm-lock.yaml": "_parse_pnpm_audit",
    "yarn.lock": "_parse_yarn_audit",
}


class PnpmAuditRunner:
    """Runs the JS dependency-audit tool matching the subproject's lockfile
    (npm audit / pnpm audit / yarn audit) for criterion 4.1.

    Despite the class name (kept to minimize the change's footprint on
    cli.py's registration and the dependency_vulnerabilities normalizer's
    pnpm-audit tool_name key), this runner audits any JS subproject
    regardless of package manager: it detects which lockfile is present
    and dispatches to the matching command. The raw `command` field on
    every result always records the real command that ran.
    """

    tool_name = "pnpm-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "package.json"
        if not manifest.exists():
            return RawToolOutput(
                command="npm/pnpm/yarn audit (skipped, no package.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        lockfile_name = self._detect_lockfile(target_path)
        if lockfile_name is None:
            return RawToolOutput(
                command="npm/pnpm/yarn audit (skipped, no lockfile)",
                raw_output={
                    "manifest_found": True,
                    "error": {
                        "code": "NO_LOCKFILE_DETECTED",
                        "summary": "None of package-lock.json, pnpm-lock.yaml, "
                        "yarn.lock found in the target directory.",
                    },
                },
                exit_code=0,
                duration_ms=0,
            )

        command = _LOCKFILE_COMMANDS[lockfile_name]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        parser = getattr(self, _PARSER_NAMES[lockfile_name])
        vulnerabilities = parser(completed.stdout)
        if vulnerabilities is None:
            return self._failed(command, completed, duration_ms)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _detect_lockfile(target_path: Path) -> str | None:
        for lockfile_name in _LOCKFILE_COMMANDS:
            if (target_path / lockfile_name).exists():
                return lockfile_name
        return None

    @staticmethod
    def _parse_npm_audit(stdout: str) -> list[dict[str, object]] | None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        if (
            not isinstance(data, dict)
            or "error" in data
            or not isinstance(data.get("vulnerabilities"), dict)
        ):
            return None

        vulnerabilities = []
        for package_name, entry in data["vulnerabilities"].items():
            for via in entry.get("via", []):
                # A string `via` entry just names another vulnerable
                # dependency this package pulls in; the real advisory is
                # reported under that dependency's own top-level entry, so
                # string entries are skipped here to avoid double-counting
                # or fabricating a malformed advisory from a bare name.
                if not isinstance(via, dict):
                    continue
                vulnerabilities.append(
                    {
                        "id": str(via["source"]),
                        "package": package_name,
                        "severity": _SEVERITY_MAP.get(via.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(entry.get("fixAvailable")),
                    }
                )
        return vulnerabilities

    @staticmethod
    def _parse_pnpm_audit(stdout: str) -> list[dict[str, object]] | None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        # pnpm reports its own failures as valid JSON with a top-level "error" key
        # (e.g. ERR_PNPM_AUDIT_NO_LOCKFILE, registry errors), confirmed empirically.
        # pnpm's success JSON always uses an object keyed by advisory id (including the
        # zero-dependency case -- `{}`, not `[]`), so anything else is a failed audit.
        if (
            not isinstance(data, dict)
            or "error" in data
            or not isinstance(data.get("advisories"), dict)
        ):
            return None

        vulnerabilities = []
        for advisory in data["advisories"].values():
            patched = advisory.get("patched_versions")
            vulnerabilities.append(
                {
                    "id": str(advisory["id"]),
                    "package": advisory["module_name"],
                    "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                    "fix_available": bool(patched) and patched != "<0.0.0",
                }
            )
        return vulnerabilities

    @staticmethod
    def _parse_yarn_audit(stdout: str) -> list[dict[str, object]] | None:
        # yarn classic prints one JSON object per line (not a single JSON
        # document): "auditAdvisory" records carry the same advisory shape
        # as pnpm's (id/module_name/severity/patched_versions), and a
        # trailing "auditSummary" record marks a completed run. Its absence
        # means yarn errored out before finishing the audit.
        vulnerabilities = []
        saw_summary = False
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return None
            if not isinstance(record, dict):
                return None
            record_type = record.get("type")
            if record_type == "auditAdvisory":
                advisory = record.get("data", {}).get("advisory", {})
                patched = advisory.get("patched_versions")
                vulnerabilities.append(
                    {
                        "id": str(advisory["id"]),
                        "package": advisory["module_name"],
                        "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(patched) and patched != "<0.0.0",
                    }
                )
            elif record_type == "auditSummary":
                saw_summary = True
        if not saw_summary:
            return None
        return vulnerabilities

    @staticmethod
    def _failed(
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        duration_ms: int,
    ) -> RawToolOutput:
        """Build the failure shape: an "error" key and no "vulnerabilities" list."""
        error = None
        try:
            data = json.loads(completed.stdout)
            if isinstance(data, dict):
                error = data.get("error")
        except json.JSONDecodeError:
            pass
        return RawToolOutput(
            command=" ".join(command),
            raw_output={
                "manifest_found": True,
                "error": error or "audit produced no usable advisories report",
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
