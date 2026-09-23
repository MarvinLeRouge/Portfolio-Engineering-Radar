from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

# uv-managed Python builds ship without ensurepip, which breaks pip-audit's own
# ephemeral venv creation unless forced onto the system Python -- per toolchain.md.
_PIP_AUDIT_PYTHON = "/usr/bin/python3.13"


class PipAuditRunner:
    """Runs pip-audit against a Python subproject's requirements.txt (criterion 4.1)."""

    tool_name = "pip-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "requirements.txt"
        if not manifest.exists():
            return RawToolOutput(
                command="pip-audit (skipped, no requirements.txt)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = [
            "uvx",
            "--python",
            _PIP_AUDIT_PYTHON,
            "pip-audit",
            "-r",
            "requirements.txt",
            "--format",
            "json",
        ]
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

        vulnerabilities = []
        for dependency in data.get("dependencies", []):
            for vuln in dependency.get("vulns", []):
                vulnerabilities.append(
                    {
                        "id": vuln["id"],
                        "package": dependency["name"],
                        "severity": "MEDIUM",  # pip-audit's JSON carries no severity field
                        "fix_available": bool(vuln.get("fix_versions")),
                    }
                )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
