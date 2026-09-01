from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")


class JscpdRunner:
    """Runs jscpd for cross-language code duplication detection (criterion 2.5)."""

    tool_name = "jscpd"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.TemporaryDirectory() as report_dir:
            ignore_patterns = [f"**/{name}/**" for name in _ALWAYS_EXCLUDED_DIRNAMES]
            for excluded in exclude_paths:
                ignore_patterns.append(f"{excluded}/**")

            command = [
                "npx",
                "--package=jscpd",
                "--",
                "jscpd",
                "--reporters",
                "json",
                "--output",
                report_dir,
                "--silent",
                "--ignore",
                ",".join(ignore_patterns),
                str(target_path),
            ]

            start = time.monotonic()
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            report_path = Path(report_dir) / "jscpd-report.json"
            if not report_path.exists():
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )
            raw_output = json.loads(report_path.read_text())

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
