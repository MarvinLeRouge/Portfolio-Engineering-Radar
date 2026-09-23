from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class SemgrepRunner:
    """Runs Semgrep's default/auto ruleset for SAST findings (criterion 4.3).

    Uses `--config auto` (the general-purpose default ruleset), not the
    authN/authZ-focused registry packs -- those are reserved for the deferred
    criterion 4.6a.
    """

    tool_name = "semgrep"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["uvx", "semgrep", "--config", "auto", "--json"]
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
                command.extend(["--exclude", str(relative)])
            except ValueError:
                pass  # not under target_path, skip
        command.append(".")

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"results": data.get("results", [])},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
