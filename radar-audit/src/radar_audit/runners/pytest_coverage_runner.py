from __future__ import annotations

import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PytestCoverageRunner:
    """Runs pytest+coverage against the target's own runtime dependencies, ephemeral
    install via uvx (criterion 3.1, Python). Never reads a committed coverage.xml --
    always a live run, per quality-framework.md 3.5's evidence-freshness rule.
    """

    tool_name = "pytest-cov"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.TemporaryDirectory() as report_dir:
            junit_path = Path(report_dir) / "junit.xml"
            coverage_path = Path(report_dir) / "coverage.xml"

            command = ["uvx", "--with", "pytest-cov"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            command.append("pytest")
            command.extend(
                [
                    f"--junitxml={junit_path}",
                    f"--cov={target_path}",
                    f"--cov-report=xml:{coverage_path}",
                    str(target_path),
                ]
            )

            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            if not junit_path.exists():
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )

            raw_output = self._parse_junit(junit_path)
            raw_output["coverage_percent"] = self._parse_coverage(coverage_path)

            return RawToolOutput(
                command=" ".join(command),
                raw_output=raw_output,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

    def _parse_junit(self, junit_path: Path) -> dict[str, object]:
        root = ET.parse(junit_path).getroot()
        suite = root.find("testsuite") if root.tag == "testsuites" else root
        if suite is None:
            return {"tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}, "failures": []}

        total = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))

        failed_cases = []
        for testcase in suite.findall("testcase"):
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                classname = testcase.get("classname")
                failed_cases.append(
                    {
                        # pytest's default --junitxml has no file/line attribute on
                        # <testcase> (only classname/name/time) -- best-effort derive
                        # a file path from classname, leave line unavailable.
                        "file": classname.replace(".", "/") + ".py" if classname else None,
                        "name": testcase.get("name"),
                        "line": None,
                    }
                )

        return {
            "tests": {
                "total": total,
                "passed": total - failures - errors - skipped,
                "failed": failures + errors,
                "skipped": skipped,
            },
            "failures": failed_cases,
        }

    def _parse_coverage(self, coverage_path: Path) -> float | None:
        if not coverage_path.exists():
            return None
        root = ET.parse(coverage_path).getroot()
        line_rate = root.get("line-rate")
        return round(float(line_rate) * 100, 2) if line_rate is not None else None
