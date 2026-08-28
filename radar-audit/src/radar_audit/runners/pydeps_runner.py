from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PydepsRunner:
    """Reports the Python import graph via pydeps, used for cycle detection (criterion 1.1).

    Uses `--show-deps --no-output --max-bacon=0` rather than `--show-cycles`: live testing
    showed `--show-cycles` produces no usable stdout even against a genuine cycle, while
    `--show-deps` reliably returns a structured JSON import graph. Cycle detection itself
    runs in the normalizer (a DFS over each module's `imports` adjacency list), not here.

    Accuracy depends on `target_path` being an actual importable package root (contains
    `__init__.py`, its directory name matching the import style used inside it) — see the
    plan's "Known limitation" note.
    """

    tool_name = "pydeps"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["uvx", "pydeps", str(target_path), "--show-deps", "--no-output", "--max-bacon=0"]

        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
