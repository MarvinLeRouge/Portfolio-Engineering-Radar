from __future__ import annotations

import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PestRunner:
    """Runs the target's own locally-installed Pest (criterion 3.1, PHP), native
    invocation via vendor/bin/pest -- same reasoning as PintRunner in 2.1. --min=0
    disables Pest's own coverage-threshold gate so exit_code reflects test pass/fail
    only. Never reads a committed coverage report -- always a live run.
    """

    tool_name = "pest"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        local_bin = target_path / "vendor" / "bin" / "pest"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"pest (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        with tempfile.TemporaryDirectory() as report_dir:
            junit_path = Path(report_dir) / "junit.xml"
            clover_path = Path(report_dir) / "clover.xml"

            command = [
                str(local_bin),
                f"--log-junit={junit_path}",
                "--coverage",
                f"--coverage-clover={clover_path}",
                "--min=0",
            ]

            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            # Pest writes an empty (0-byte) junit.xml -- not "file absent" -- when it
            # fails before running any test (e.g. a misconfigured/missing tests/
            # directory triggers "Test directory not found", exit 2). Guard against
            # both "no report file" and "unparseable/empty report file" the same way.
            no_usable_report = not junit_path.exists()
            if not no_usable_report:
                try:
                    raw_output = self._parse_junit(junit_path)
                except ET.ParseError:
                    no_usable_report = True

            if no_usable_report:
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={
                        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                        "failures": [],
                        "coverage_percent": None,
                    },
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )

            raw_output["coverage_percent"] = self._parse_clover(clover_path)

            return RawToolOutput(
                command=" ".join(command),
                raw_output=raw_output,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

    def _parse_junit(self, junit_path: Path) -> dict[str, object]:
        root = ET.parse(junit_path).getroot()
        # Pest's zero-tests case is a bare <testsuites/> with NO child <testsuite> at
        # all (unlike pytest, which still emits a tests="0" element) -- guard for it.
        suite = root.find("testsuite") if root.tag == "testsuites" else root
        if suite is None:
            return {"tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}, "failures": []}

        total = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))

        failed_cases = []
        for testcase in suite.iter("testcase"):
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                # Pest's testcase file attribute is "path/to/Test.php::testname" --
                # strip the "::name" suffix. No line attribute is provided.
                raw_file = testcase.get("file")
                failed_cases.append(
                    {
                        "file": raw_file.split("::")[0] if raw_file else None,
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

    def _parse_clover(self, clover_path: Path) -> float | None:
        if not clover_path.exists():
            return None
        root = ET.parse(clover_path).getroot()
        metrics = root.find(".//project/metrics")
        if metrics is None:
            return None
        statements = int(metrics.get("statements", 0))
        covered = int(metrics.get("coveredstatements", 0))
        if statements == 0:
            return None
        return round((covered / statements) * 100, 2)
