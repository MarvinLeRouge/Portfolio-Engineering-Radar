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


class PnpmAuditRunner:
    """Runs `pnpm audit` against a JavaScript subproject (criterion 4.1)."""

    tool_name = "pnpm-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "package.json"
        if not manifest.exists():
            return RawToolOutput(
                command="pnpm audit (skipped, no package.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = ["pnpm", "audit", "--json"]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            data = json.loads(completed.stdout)
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

        # pnpm's own JSON always uses an object keyed by advisory id here (confirmed
        # empirically, including the zero-dependency case -- `{}`, not `[]`).
        advisories = data.get("advisories", {})
        vulnerabilities = []
        if isinstance(advisories, dict):
            for advisory in advisories.values():
                patched = advisory.get("patched_versions")
                vulnerabilities.append(
                    {
                        "id": str(advisory["id"]),
                        "package": advisory["module_name"],
                        "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(patched) and patched != "<0.0.0",
                    }
                )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
