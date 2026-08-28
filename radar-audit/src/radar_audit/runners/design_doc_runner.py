from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_DOC_FILENAMES = ("DESIGN.MD", "ARCHITECTURE.MD")
_ADR_DIRNAMES = ("adr", "decisions")


class DesignDocRunner:
    """Checks for DESIGN.md/ARCHITECTURE.md/ADR presence (criterion 1.2). No subprocess."""

    tool_name = "design-doc-presence"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        found_path, non_blank_lines = self._find_doc(target_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"filesystem-check {target_path}",
            raw_output={
                "found_path": str(found_path) if found_path is not None else None,
                "non_blank_lines": non_blank_lines,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _find_doc(self, target_path: Path) -> tuple[Path | None, int]:
        for directory in (target_path, target_path / "docs"):
            doc_path = self._find_named_file(directory)
            if doc_path is not None:
                return doc_path, self._count_non_blank_lines(doc_path)

        for adr_dirname in _ADR_DIRNAMES:
            adr_dir = target_path / "docs" / adr_dirname
            if adr_dir.is_dir():
                md_files = sorted(adr_dir.glob("*.md"))
                if md_files:
                    total_lines = sum(self._count_non_blank_lines(f) for f in md_files)
                    return adr_dir, total_lines

        return None, 0

    def _find_named_file(self, directory: Path) -> Path | None:
        if not directory.is_dir():
            return None
        for entry in directory.iterdir():
            if entry.is_file() and entry.name.upper() in _DOC_FILENAMES:
                return entry
        return None

    def _count_non_blank_lines(self, file_path: Path) -> int:
        return sum(1 for line in file_path.read_text().splitlines() if line.strip())
