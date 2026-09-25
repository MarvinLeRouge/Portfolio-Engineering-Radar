from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class DocvetRunner:
    """Runs docvet's docstring presence check with an audit-owned scratch config.

    Criterion 5.3, Python.
    """

    tool_name = "docvet"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        exclude_entries = []
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue
            if relative == Path("."):
                exclude_entries.append("*")
            else:
                exclude_entries.append(str(relative))

        config_content = "[tool.docvet]\n" f"exclude = {json.dumps(exclude_entries)}\n"

        with tempfile.NamedTemporaryFile(
            "w", suffix=".toml", delete=False, dir=target_path
        ) as config_file:
            config_file.write(config_content)
            config_path = Path(config_file.name)

        try:
            command = [
                "uvx",
                "docvet",
                "--format",
                "json",
                "--config",
                config_path.name,
                "presence",
                "--all",
            ]
            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)
        finally:
            config_path.unlink(missing_ok=True)

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
