from __future__ import annotations

import json
import re
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class MypyRunner:
    """Runs mypy (criterion 2.2, Python), branching on plugin detection per toolchain.md."""

    tool_name = "mypy"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        if self._has_plugin(target_path):
            command = ["uvx", "--with", "mypy"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            command.extend(["mypy", "--output=json", "--ignore-missing-imports"])
        else:
            command = ["uvx", "mypy", "--output=json", "--ignore-missing-imports"]

        if exclude_paths:
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                    # Use regex-escaped path for mypy's --exclude (which expects regex)
                    command.extend(["--exclude", re.escape(str(relative))])
                except ValueError:
                    pass  # not under target_path, skip

        command.append(str(target_path))

        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
        duration_ms = int((time.monotonic() - start) * 1000)

        diagnostics = []
        for line in completed.stdout.splitlines():
            try:
                diagnostics.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        total_files = self._count_python_files(target_path, exclude_paths)
        return RawToolOutput(
            command=" ".join(command),
            raw_output={"diagnostics": diagnostics, "total_files": total_files},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _has_plugin(self, target_path: Path) -> bool:
        pyproject = target_path / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            if data.get("tool", {}).get("mypy", {}).get("plugins"):
                return True
        mypy_ini = target_path / "mypy.ini"
        if mypy_ini.exists() and "plugins" in mypy_ini.read_text():
            return True
        return False

    def _count_python_files(self, target_path: Path, exclude_paths: list[Path]) -> int:
        count = 0
        for file_path in target_path.rglob("*.py"):
            if not file_path.is_file():
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
