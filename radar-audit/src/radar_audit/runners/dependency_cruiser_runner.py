from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

# Directory names always excluded regardless of exclude_paths: --no-config disables
# dependency-cruiser's own default node_modules exclusion, and none of these hold
# code written by the audited project -- node_modules is vendored, dist/build are
# compiled/bundled output (e.g. a Vite build under public/build).
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "dist", "build")


class DependencyCruiserRunner:
    """Detects circular JS/TS dependencies via dependency-cruiser (criterion 1.1)."""

    tool_name = "dependency-cruiser"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = [
            "npx",
            "--package=dependency-cruiser",
            "--",
            "depcruise",
            "--no-config",
            "--output-type",
            "json",
        ]
        command.extend(["-x", self._build_exclude_pattern(target_path, exclude_paths)])
        command.append(".")

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
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

    def _build_exclude_pattern(self, target_path: Path, exclude_paths: list[Path]) -> str:
        relative_patterns = [rf"(^|/){re.escape(name)}(/|$)" for name in _ALWAYS_EXCLUDED_DIRNAMES]
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue  # not under target_path, dependency-cruiser will never visit it
            relative_patterns.append(re.escape(relative.as_posix()))
        return "|".join(relative_patterns)
