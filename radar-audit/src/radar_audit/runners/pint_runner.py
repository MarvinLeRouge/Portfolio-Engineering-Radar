from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PintRunner:
    """Runs the target's own locally-installed Laravel Pint (criterion 2.1)."""

    tool_name = "pint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        local_bin = target_path / "vendor" / "bin" / "pint"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"pint (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        command = [str(local_bin), "--test", "--format=json"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
