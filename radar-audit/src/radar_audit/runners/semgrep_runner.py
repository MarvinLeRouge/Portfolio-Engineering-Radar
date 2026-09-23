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
            data = None

        if not _scan_succeeded(data, completed.returncode):
            # Failure shape: an "error" key and no "results" list, so the normalizer
            # never mistakes a failed scan for a clean one.
            errors = data.get("errors") if isinstance(data, dict) else None
            return RawToolOutput(
                command=" ".join(command),
                raw_output={
                    "error": "semgrep scan failed",
                    "errors": errors or [],
                    "stdout": completed.stdout if data is None else "",
                    "stderr": completed.stderr,
                },
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"results": data["results"]},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )


def _scan_succeeded(data: object, returncode: int) -> bool:
    """Tell whether semgrep's JSON report reflects a scan that actually ran.

    Exit codes >= 2 are semgrep hard failures (e.g. 7 for a rule download failure,
    confirmed empirically). Per-file "warn"-level errors (a file that failed to parse)
    come with exit code 0 and leave the rest of the scan valid, but an "error"-level
    entry alongside empty results means the scan itself did not run.
    """
    if returncode >= 2 or not isinstance(data, dict):
        return False
    results = data.get("results")
    if not isinstance(results, list):
        return False
    errors = data.get("errors") or []
    has_fatal_error = any(
        isinstance(error, dict) and error.get("level") == "error" for error in errors
    )
    return bool(results) or not has_fatal_error
