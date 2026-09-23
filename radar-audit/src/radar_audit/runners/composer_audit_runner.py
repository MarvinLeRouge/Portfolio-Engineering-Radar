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
    "medium": "MEDIUM",
    "low": "LOW",
}


class ComposerAuditRunner:
    """Runs `composer audit` against a PHP subproject (criterion 4.1)."""

    tool_name = "composer-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "composer.json"
        if not manifest.exists():
            return RawToolOutput(
                command="composer audit (skipped, no composer.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = ["composer", "audit", "--format=json"]
        # --locked audits composer.lock directly, so a checkout without an installed
        # vendor/ is still audited (without it, composer only audits installed packages).
        if (target_path / "composer.lock").exists():
            command.append("--locked")
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # With zero packages to audit, `composer audit` prints nothing to stdout
        # ("No packages - skipping audit." goes to stderr instead) - confirmed
        # empirically. That is only a clean result when the manifest declares no
        # package dependencies; otherwise the audit never actually ran.
        stdout = completed.stdout.strip()
        if not stdout:
            if _declares_package_dependencies(manifest):
                return self._failed(command, completed, duration_ms, "no packages were audited")
            data: object = {"advisories": []}
        else:
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                data = None

        # Composer's own JSON uses an object keyed by package name when advisories
        # exist, but an empty *array* (not `{}`) when none do - confirmed
        # empirically; both shapes must be handled without crashing. Any other shape
        # is a failed audit.
        advisories = data.get("advisories") if isinstance(data, dict) else None
        if not isinstance(advisories, dict | list):
            return self._failed(
                command, completed, duration_ms, "composer audit produced no advisories report"
            )
        vulnerabilities = []
        if isinstance(advisories, dict):
            for package_advisories in advisories.values():
                for advisory in package_advisories:
                    vulnerabilities.append(
                        {
                            "id": advisory["advisoryId"],
                            "package": advisory["packageName"],
                            "severity": _SEVERITY_MAP.get(
                                (advisory.get("severity") or "").lower(), "MEDIUM"
                            ),
                            "fix_available": True,
                        }
                    )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _failed(
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        duration_ms: int,
        error: str,
    ) -> RawToolOutput:
        """Build the failure shape: an "error" key and no "vulnerabilities" list."""
        return RawToolOutput(
            command=" ".join(command),
            raw_output={
                "manifest_found": True,
                "error": error,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )


def _declares_package_dependencies(manifest: Path) -> bool:
    """Tell whether composer.json requires any real package (vendor/name form).

    Platform requirements (php, ext-*, lib-*) have no slash and are never audited. An
    unreadable manifest is conservatively treated as declaring dependencies.
    """
    try:
        data = json.loads(manifest.read_text())
    except (OSError, json.JSONDecodeError):
        return True
    if not isinstance(data, dict):
        return True
    for section in ("require", "require-dev"):
        requirements = data.get(section) or {}
        if isinstance(requirements, dict) and any("/" in name for name in requirements):
            return True
    return False
