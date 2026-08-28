from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_GLOB_SUFFIXES = (
    "/.venv/*",
    "/__pycache__/*",
    "/node_modules/*",
    "/vendor/*",
    "/dist/*",
    "/build/*",
)


class RadonModuleSizeRunner:
    """Reports per-file LOC for Python modules via radon (criterion 1.3)."""

    tool_name = "radon-raw"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        # Exclude glob patterns must be absolute (matching `target_path`'s own form).
        # radon's exclude matching was empirically found not to match relative globs
        # when radon is invoked with an absolute target_path.
        patterns = [f"{target_path}{suffix}" for suffix in _SKIP_GLOB_SUFFIXES]
        patterns.extend(f"{excluded}/*" for excluded in exclude_paths)

        command = ["uvx", "radon", "raw", "--json", "-e", ",".join(patterns), str(target_path)]

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
