from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RawToolOutput:
    command: str
    raw_output: dict[str, object]
    exit_code: int
    duration_ms: int


class ToolRunner(Protocol):
    tool_name: str
    tool_version: str

    def run(self, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput: ...
