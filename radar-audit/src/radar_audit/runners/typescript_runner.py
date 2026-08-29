from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from radar_audit.runner import RawToolOutput

_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\): error (?P<code>TS\d+): (?P<message>.+)$"
)
_SOURCE_EXTENSIONS = {".ts", ".tsx", ".vue"}
_SKIP_DIRNAMES = {"node_modules", "dist", "build"}


class TypeScriptRunner:
    """Runs an ephemeral tsc/vue-tsc against the target's own tsconfig.json (criterion 2.2)."""

    tool_name = "tsc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        package_json = target_path / "package.json"
        data = json.loads(package_json.read_text()) if package_json.exists() else {}
        package_name, binary_name = self._resolve_package_and_binary(data)

        command = ["npx", f"--package={package_name}", "--", binary_name, "--noEmit"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        diagnostics = []
        for line in completed.stdout.splitlines():
            match = _DIAGNOSTIC_PATTERN.match(line.strip())
            if match:
                diagnostics.append(
                    {
                        "file": match.group("file"),
                        "line": int(match.group("line")),
                        "column": int(match.group("column")),
                        "code": match.group("code"),
                        "message": match.group("message"),
                    }
                )

        total_files = self._count_source_files(target_path, exclude_paths)
        return RawToolOutput(
            command=" ".join(command),
            raw_output={"diagnostics": diagnostics, "total_files": total_files},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _resolve_package_and_binary(self, package_json_data: dict[str, Any]) -> tuple[str, str]:
        dev_dependencies: dict[str, Any] = package_json_data.get("devDependencies", {})
        if "vue-tsc" in dev_dependencies:
            return "vue-tsc", "vue-tsc"
        return "typescript", "tsc"

    def _count_source_files(self, target_path: Path, exclude_paths: list[Path]) -> int:
        count = 0
        for file_path in target_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            count += 1
        return count

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(
            excluded == file_path or excluded in file_path.parents for excluded in exclude_paths
        )
