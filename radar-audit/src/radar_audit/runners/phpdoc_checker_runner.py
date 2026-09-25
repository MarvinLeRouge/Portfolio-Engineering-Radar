from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PhpdocCheckerRunner:
    """Runs php-censor/phpdoc-checker from its own isolated scratch Composer project.

    Criterion 5.3, PHP.
    """

    tool_name = "phpdoc-checker"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as scratch_dir:
            scratch = Path(scratch_dir)
            subprocess.run(
                [
                    "composer",
                    "init",
                    "--no-interaction",
                    "--name=radar-audit/phpdoc-checker-scratch",
                ],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            subprocess.run(
                ["composer", "require", "--dev", "php-censor/phpdoc-checker", "--no-interaction"],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )

            patterns = ["vendor"]
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                except ValueError:
                    continue
                patterns.append(str(relative))

            command = [
                str(scratch / "vendor" / "bin" / "phpdoc-checker"),
                "-d",
                str(target_path),
                "-x",
                ",".join(patterns),
                "-j",
            ]

            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout_s
            )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            findings = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"findings": findings},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
