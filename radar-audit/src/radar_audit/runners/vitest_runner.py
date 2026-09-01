from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class VitestRunner:
    """Runs the target's own locally-installed Vitest (criterion 3.1, JavaScript).

    Native invocation, same reasoning as PintRunner/PestRunner: measures the repo's
    own configured test suite, not an audit-owned tool version. The ephemeral
    `npx --package=vitest --package=@vitest/coverage-v8` pattern was tried during
    plan-writing and fails (ERESOLVE on unpinned versions; "Cannot find package" at
    runtime even with pinned matching versions) -- resolved by invoking the target's
    own node_modules/.bin/vitest directly instead.

    `exclude_paths` (other git worktrees of the same repo) is forwarded as one
    `--exclude` glob per path -- Vitest's own default test glob recurses the whole
    project tree, so a worktree checked out under the repo (e.g.
    `.claude/worktrees/<branch>/`) is otherwise collected a second time, inflating
    counts and, if that worktree carries stale/foreign spec files (e.g. Playwright
    `.spec.js` files that don't parse as Vitest tests), failing the whole run.
    """

    tool_name = "vitest"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        local_bin = target_path / "node_modules" / ".bin" / "vitest"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"vitest (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        has_coverage_provider = (target_path / "node_modules" / "@vitest" / "coverage-v8").exists()

        with tempfile.TemporaryDirectory() as report_dir:
            report_path = Path(report_dir) / "report.json"
            coverage_dir = Path(report_dir) / "coverage"

            command = [str(local_bin), "run", "--reporter=json", f"--outputFile={report_path}"]
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                except ValueError:
                    continue
                command.extend(["--exclude", f"{relative}/**"])
            if has_coverage_provider:
                command += [
                    "--coverage",
                    "--coverage.reporter=json-summary",
                    f"--coverage.reportsDirectory={coverage_dir}",
                ]

            start = time.monotonic()
            completed = subprocess.run(
                command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            if not report_path.exists():
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

            report = json.loads(report_path.read_text())
            raw_output = self._to_raw_output(report)

            coverage_summary_path = coverage_dir / "coverage-summary.json"
            if has_coverage_provider and coverage_summary_path.exists():
                coverage_data = json.loads(coverage_summary_path.read_text())
                raw_output["coverage_percent"] = (
                    coverage_data.get("total", {}).get("lines", {}).get("pct")
                )
            else:
                raw_output["coverage_percent"] = None

            return RawToolOutput(
                command=" ".join(command),
                raw_output=raw_output,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

    def _to_raw_output(self, report: dict[str, object]) -> dict[str, object]:
        total = report.get("numTotalTests", 0)
        passed = report.get("numPassedTests", 0)
        failed = report.get("numFailedTests", 0)
        skipped = report.get("numPendingTests", 0)

        failures = []
        for test_result in report.get("testResults", []):  # type: ignore[attr-defined]
            file_path = test_result.get("name")
            for assertion in test_result.get("assertionResults", []):
                if assertion.get("status") == "failed":
                    # Vitest's JSON reporter has no location/line field on
                    # assertionResults -- file comes from the parent testResults
                    # entry, line stays unavailable (same limitation as pytest/Pest).
                    failures.append(
                        {
                            "file": file_path,
                            "name": assertion.get("fullName") or assertion.get("title"),
                            "line": None,
                        }
                    )

        return {
            "tests": {"total": total, "passed": passed, "failed": failed, "skipped": skipped},
            "failures": failures,
        }
