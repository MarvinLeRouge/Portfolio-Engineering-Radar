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


class RadonComplexityRunner:
    """Runs radon's cyclomatic complexity analysis (criterion 2.3, Python)."""

    tool_name = "radon-cc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        patterns = [f"{target_path}{suffix}" for suffix in _SKIP_GLOB_SUFFIXES]
        patterns.extend(f"{excluded}/*" for excluded in exclude_paths)
        command = ["uvx", "radon", "cc", "--json", "-e", ",".join(patterns), str(target_path)]

        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
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
