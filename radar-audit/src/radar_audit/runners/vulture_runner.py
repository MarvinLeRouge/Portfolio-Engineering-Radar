from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_GLOB_SUFFIXES = (
    "/.venv/*",
    "/__pycache__/*",
    "/node_modules/*",
    "/vendor/*",
    "/dist/*",
    "/build/*",
)
_IGNORE_DECORATORS = "@app.command,@app.callback"
_LINE_PATTERN = re.compile(
    r"^(?P<file>.+):(?P<line>\d+): unused (?P<kind>\S+) '(?P<name>[^']+)' "
    r"\((?P<confidence>\d+)% confidence\)$"
)


class VultureRunner:
    """Runs vulture's dead-code detection (criterion 5.2, Python)."""

    tool_name = "vulture"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        patterns = [f"{target_path}{suffix}" for suffix in _SKIP_GLOB_SUFFIXES]
        patterns.extend(f"{excluded}/*" for excluded in exclude_paths)
        command = [
            "uvx",
            "vulture",
            str(target_path),
            "--ignore-decorators",
            _IGNORE_DECORATORS,
            "--exclude",
            ",".join(patterns),
        ]

        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
        duration_ms = int((time.monotonic() - start) * 1000)

        findings = []
        for line in completed.stdout.splitlines():
            match = _LINE_PATTERN.match(line.strip())
            if match:
                findings.append(
                    {
                        "file": match.group("file"),
                        "line": int(match.group("line")),
                        "kind": match.group("kind"),
                        "name": match.group("name"),
                        "confidence": int(match.group("confidence")),
                    }
                )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"findings": findings},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
