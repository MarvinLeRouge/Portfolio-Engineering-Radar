from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


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
        exclude_pattern = self._build_exclude_pattern(target_path, exclude_paths)
        if exclude_pattern is not None:
            command.extend(["-x", exclude_pattern])
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

    def _build_exclude_pattern(self, target_path: Path, exclude_paths: list[Path]) -> str | None:
        relative_patterns = []
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue  # not under target_path, dependency-cruiser will never visit it
            relative_patterns.append(re.escape(relative.as_posix()))
        return "|".join(relative_patterns) if relative_patterns else None
