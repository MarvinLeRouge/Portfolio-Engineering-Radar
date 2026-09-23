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
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # With zero installed packages, `composer audit` prints nothing to stdout
        # ("No packages - skipping audit." goes to stderr instead) - confirmed
        # empirically. Treat that the same as an explicit empty advisories list.
        stdout = completed.stdout.strip()
        try:
            data = json.loads(stdout) if stdout else {"advisories": []}
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={
                    "manifest_found": True,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        # Composer's own JSON uses an object keyed by package name when advisories
        # exist, but an empty *array* (not `{}`) when none do - confirmed
        # empirically; both shapes must be handled without crashing.
        advisories = data.get("advisories", [])
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
