from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SOURCE_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".vue", ".php"}
_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class StaticLocRunner:
    """Counts non-blank lines per JS/TS/Vue/PHP source file via a plain filesystem walk
    (criterion 1.3 — no dedicated LOC tool validated for these stacks, see toolchain.md).
    """

    tool_name = "static-loc-count"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript", "php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        per_file: dict[str, int] = {}
        for file_path in sorted(target_path.rglob("*")):
            if not file_path.is_file() or file_path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if self._is_skipped(file_path, exclude_paths):
                continue
            per_file[str(file_path)] = self._count_non_blank_lines(file_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"static-loc-walk {target_path}",
            raw_output={"files": per_file},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _is_skipped(self, file_path: Path, exclude_paths: list[Path]) -> bool:
        if any(part in _SKIP_DIRNAMES for part in file_path.parts):
            return True
        return any(
            excluded == file_path or excluded in file_path.parents for excluded in exclude_paths
        )

    def _count_non_blank_lines(self, file_path: Path) -> int:
        return sum(1 for line in file_path.read_text(errors="ignore").splitlines() if line.strip())
