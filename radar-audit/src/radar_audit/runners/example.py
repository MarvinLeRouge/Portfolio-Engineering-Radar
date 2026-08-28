from __future__ import annotations

import subprocess
import time
from pathlib import Path

from radar_audit.runner import RawToolOutput


class ExampleGitLogRunner:
    """Throwaway proof-of-pipeline runner. Removed once increment 2.1 adds real tools."""

    tool_name = "example-git-log"
    tool_version = "1.0.0"

    def run(self, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["git", "-C", str(subproject_path), "log", "-1", "--format=%H"]
        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True)
        duration_ms = int((time.monotonic() - start) * 1000)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
