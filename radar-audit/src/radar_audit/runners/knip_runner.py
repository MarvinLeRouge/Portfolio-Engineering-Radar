from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_DEFAULT_ENTRY_CANDIDATES = (
    "index.html",
    "src/main.js",
    "src/main.ts",
    "src/main.jsx",
    "src/main.tsx",
)
_JSON_PREFIX = '{"issues"'


class KnipRunner:
    """Runs knip's unused-exports detection with audit-owned config (criterion 5.2, JS)."""

    tool_name = "knip"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        entries = [c for c in _DEFAULT_ENTRY_CANDIDATES if (target_path / c).exists()]
        if not entries:
            return RawToolOutput(
                command="",
                raw_output={"issues": []},
                exit_code=0,
                duration_ms=0,
            )

        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, dir=target_path
        ) as config_file:
            json.dump({"entry": entries}, config_file)
            config_path = Path(config_file.name)

        try:
            command = [
                "npx",
                "--package=knip",
                "--",
                "knip",
                "--config",
                config_path.name,
                "--reporter",
                "json",
            ]
            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)
        finally:
            config_path.unlink(missing_ok=True)

        prefix_index = completed.stdout.find(_JSON_PREFIX)
        if prefix_index == -1:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        try:
            raw_output = json.loads(completed.stdout[prefix_index:])
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
