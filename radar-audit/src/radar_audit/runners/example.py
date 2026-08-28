from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class ExampleGitLogRunner:
    """Throwaway proof-of-pipeline runner. Removed once the real category-1 runners land."""

    tool_name = "example-git-log"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"unknown", "python", "javascript", "php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["git", "-C", str(target_path), "log", "-1", "--format=%H"]
        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
        duration_ms = int((time.monotonic() - start) * 1000)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
