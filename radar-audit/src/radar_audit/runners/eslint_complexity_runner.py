from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_AUDIT_CONFIG = 'module.exports = [{ rules: { complexity: ["error", 0] } }];\n'
_COMPLEXITY_PATTERN = re.compile(r"complexity of (\d+)")


class EslintComplexityRunner:
    """Run ESLint with audit-owned ["error", 0] complexity config (criterion 2.3)."""

    tool_name = "eslint-complexity"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".config.cjs", delete=False, dir=target_path
        ) as config_file:
            config_file.write(_AUDIT_CONFIG)
            config_path = Path(config_file.name)

        try:
            command = [
                "npx",
                "--package=eslint",
                "--",
                "eslint",
                "-c",
                str(config_path),
                str(target_path),
                "--format",
                "json",
            ]
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                except ValueError:
                    continue  # not under target_path, skip
                command.extend(["--ignore-pattern", f"{relative}/**"])

            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)
        finally:
            config_path.unlink(missing_ok=True)

        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        complexities = []
        for entry in results:
            for message in entry.get("messages", []):
                match = _COMPLEXITY_PATTERN.search(message.get("message", ""))
                if match:
                    complexities.append(
                        {
                            "file": entry["filePath"],
                            "line": message.get("line"),
                            "complexity": int(match.group(1)),
                        }
                    )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"complexities": complexities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
