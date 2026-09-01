from __future__ import annotations

import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_COMPLEXITY_PATTERN = re.compile(r"Cyclomatic Complexity of (\d+)")


class PhpmdComplexityRunner:
    """Runs PHPMD's codesize ruleset from an isolated scratch Composer project (criterion 2.3)."""

    tool_name = "phpmd-codesize"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as scratch_dir:
            scratch = Path(scratch_dir)
            subprocess.run(
                ["composer", "init", "--no-interaction", "--name=radar-audit/phpmd-scratch"],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            subprocess.run(
                ["composer", "require", "--dev", "phpmd/phpmd", "--no-interaction"],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            command = [
                str(scratch / "vendor" / "bin" / "phpmd"),
                str(target_path),
                "xml",
                "codesize",
            ]

            # Build exclude patterns: always exclude vendor/*, plus any exclude_paths
            patterns = ["vendor/*"]
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                except ValueError:
                    continue
                patterns.append(f"{relative}/*")
            command.append(f"--exclude={','.join(patterns)}")

            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout_s
            )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            root = ET.fromstring(completed.stdout)
        except ET.ParseError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"violations": [], "stdout": completed.stdout},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        violations = []
        for file_element in root.findall("file"):
            file_name = file_element.get("name")
            for violation in file_element.findall("violation"):
                match = _COMPLEXITY_PATTERN.search(violation.text or "")
                if match:
                    violations.append(
                        {
                            "file": file_name,
                            "line": int(violation.get("beginline", 0)),
                            "complexity": int(match.group(1)),
                        }
                    )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"violations": violations},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
