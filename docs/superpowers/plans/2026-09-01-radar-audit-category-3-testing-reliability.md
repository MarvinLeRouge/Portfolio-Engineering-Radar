# Radar-audit Category 3 (Testing & Reliability) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 6 real `ToolRunner`s and 4 normalizers covering Quality Framework category 3 ("Testing & reliability"): Unit tests present & passing with coverage, Integration tests, E2E tests, CI executes the test suite — across Python, JavaScript/TypeScript, and PHP. Criterion 3.5 (test quality/relevance, narrow LLM-judgment layer) is out of scope, deferred alongside 1.4.

**Architecture:** Same shape as increments 2.1/2.2: each criterion gets one or more `ToolRunner` classes producing a `RawToolOutput`, and one normalizer function that reads `ToolResult` rows for the relevant `tool_name`s and writes `Score`/`Finding` rows via the existing `get_or_create_scoring_run`/`get_criterion` helpers. No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration.

**Tech Stack:** Python 3.12, SQLModel, pytest, uv/uvx (pytest+pytest-cov), native npm-installed Vitest, native Composer-installed Pest, PyYAML (already a project dependency).

**Spec:** `docs/superpowers/specs/2026-09-01-radar-audit-category-3-testing-reliability-design.md`, as corrected by the follow-up commit fixing `VitestRunner`'s invocation (§4/§11 — see Global Constraints below).

## Global Constraints

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration (spec §2/§11).
- **`VitestRunner` invocation, corrected during plan-writing.** The spec's original `npx --package=vitest --package=@vitest/coverage-v8` invocation was empirically tested and fails: unpinned versions hit an `ERESOLVE` peer-dependency conflict; pinned matching versions install cleanly but Vitest then throws `Cannot find package '@vitest/coverage-v8'` at runtime. `VitestRunner` instead invokes the target's own locally-installed binary directly (`node_modules/.bin/vitest`), same reasoning already used for `PintRunner`/`PestRunner` (measure the repo's own configured test suite, not an audit-owned tool version). This exception to the npx-pinning rule was confirmed working: coverage flags are added only when `node_modules/@vitest/coverage-v8` is also present locally; otherwise the runner still reports pass/fail without a coverage percentage.
- **`PestRunner` fixture requirement, confirmed during plan-writing.** A bare `composer.json` + test file is not enough — Pest requires a `phpunit.xml` with a `<source><include>` block pointing at a real, coverable source directory, or coverage collection throws `Pest\Exceptions\ShouldNotHappen`. Every `PestRunner` test fixture must include a minimal `phpunit.xml` and at least one non-test PHP source file under the directory that `phpunit.xml` declares as coverable.
- **JUnit/JSON `file`/`line` extraction is best-effort and tool-specific, confirmed empirically during plan-writing:** pytest's default `--junitxml` output has no `file`/`line` attribute on `<testcase>` (only `classname`/`name`/`time`), so `PytestCoverageRunner` derives `file` from `classname` (dots to slashes, `.py` appended) and leaves `line` as `None`. Pest's `<testcase>` does carry a `file` attribute (as `path::testname`, split on `::`) but no `line`. Vitest's JSON reporter's `assertionResults` have no `location`/`line` field either — `file` comes from the parent `testResults[].name`. `line` is `None` for all three tools; this is a deliberate, documented simplification, not a bug to fix later.
- **Zero-collected-tests exit codes differ per tool, confirmed empirically:** pytest exits `5` with a valid empty `<testsuite tests="0">` element. Pest exits `0` with a bare `<testsuites/>` (no child `<testsuite>` element at all — parsers must guard for a missing child, not just a `tests="0"` attribute). Vitest's zero-collected behavior is not exercised by any fixture in this plan (JS fixtures always ship at least one test file); if it comes up during Task 11's real-world validation, treat it the same way — `tests.total == 0` drives `N/A`, not a specific exit code.
- Coverage percent is optional (`None` allowed) for all three unit-test runners — a missing coverage provider or an unparseable report must not crash the runner or block the pass-rate score.
- `IntegrationTestRunner` and `CiWorkflowRunner` are `scope="repo"`, no subprocess. `PytestCoverageRunner`, `VitestRunner`, `PestRunner`, `PlaywrightPresenceRunner` are `scope="subproject"`.
- Archetype B (3.1) aggregation: summed-ratio across every relevant `ToolResult` (`tests_passed`/`tests_collected` summed, then `score = (passed / collected) * 10`) — same pattern as `module_size.py`.
- 3.2, 3.4: repo-scope, never more than one relevant `ToolResult` per audit — no aggregation rule needed.
- 3.3: worst-status-wins aggregation across every `PlaywrightPresenceRunner` result, paired with the single `CiWorkflowRunner` result for the CI-wiring signal.
- Missing-data/N/A is represented by returning `None` (no `Score` row created) — same convention as every existing normalizer.
- The §3.4 integration-test-ratio bands (0%→0, 0-10%→4, 10-25%→6, 25-50%→8, >50%→10) are resolved-but-provisional, not yet calibrated against real portfolio data — same discipline as every prior increment's thresholds.
- `Score` rows this plan writes are `ScoreLevel.CRITERION` only.
- Tests use real `uvx`/native `npm`/native `composer` invocations and real PyYAML parsing against `tmp_path` git fixtures — no mocking of subprocess or tool output.
- A real end-to-end audit run against an actual portfolio repo (Summit-Stats and/or GeoChallenge-Tracker) is required before the increment is considered done — Task 11.

---

### Task 1: `PytestCoverageRunner` (criterion 3.1, Python)

**Files:**
- Create: `src/radar_audit/runners/pytest_coverage_runner.py`
- Test: `tests/test_pytest_coverage_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner` (existing).
- Produces: `PytestCoverageRunner` with `tool_name="pytest-cov"`, `scope="subproject"`, `supported_stacks=frozenset({"python"})`. `raw_output` shape: `{"tests": {"total": int, "passed": int, "failed": int, "skipped": int}, "failures": [{"file": str|None, "name": str|None, "line": None}], "coverage_percent": float|None}`. Task 4 (`normalize_unit_test_pass_rate`) consumes this exact shape from all three 3.1 runners.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pytest_coverage_runner.py
from radar_audit.runners.pytest_coverage_runner import PytestCoverageRunner

from tests.git_helpers import init_git_repo


def test_reports_full_pass_and_coverage(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_add.py": (
                "def add(a, b):\n"
                "    return a + b\n\n\n"
                "def test_add():\n"
                "    assert add(1, 2) == 3\n"
            ),
        },
    )

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 1
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


def test_reports_failures_with_best_effort_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_add.py": (
                "def add(a, b):\n"
                "    return a + b\n\n\n"
                "def test_add():\n"
                "    assert add(1, 2) == 4\n"
            ),
        },
    )

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "tests/test_add.py"


def test_reports_zero_collected_as_no_tests(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"tests/helper.py": "def not_a_test():\n    pass\n"})

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 5
    assert result.raw_output["tests"]["total"] == 0
    assert result.raw_output["coverage_percent"] is None


def test_reports_tool_identity():
    runner = PytestCoverageRunner()

    assert runner.tool_name == "pytest-cov"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pytest_coverage_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pytest_coverage_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/pytest_coverage_runner.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_pytest_coverage_runner.py -v`
Expected: PASS, all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pytest_coverage_runner.py radar-audit/tests/test_pytest_coverage_runner.py
git commit -m "feat(radar-audit): add PytestCoverageRunner for criterion 3.1 (Python)"
```

---

### Task 2: `VitestRunner` (criterion 3.1, JavaScript)

**Files:**
- Create: `src/radar_audit/runners/vitest_runner.py`
- Test: `tests/test_vitest_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner`.
- Produces: `VitestRunner` with `tool_name="vitest"`, `scope="subproject"`, `supported_stacks=frozenset({"javascript"})`. Same `raw_output` shape as Task 1: `{"tests": {...}, "failures": [...], "coverage_percent": float|None}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vitest_runner.py
import subprocess

import pytest
from radar_audit.runners.vitest_runner import VitestRunner

from tests.git_helpers import init_git_repo


def _install_local_vitest(repo_path, with_coverage=True):
    dev_deps = '"vitest": "^3.2.7"'
    if with_coverage:
        dev_deps += ', "@vitest/coverage-v8": "^3.2.7"'
    (repo_path / "package.json").write_text(
        '{"name": "fixture", "version": "1.0.0", "type": "module", '
        '"devDependencies": {' + dev_deps + "}}\n"
    )
    subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_pass_and_coverage_on_passing_suite(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


@pytest.mark.slow
def test_reports_failures_with_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(4); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] is not None


@pytest.mark.slow
def test_reports_no_coverage_percent_when_provider_absent(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path, with_coverage=False)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["coverage_percent"] is None


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.js": "export function add() {}\n"})

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = VitestRunner()

    assert runner.tool_name == "vitest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_vitest_runner.py -v -m ""`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.vitest_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/vitest_runner.py
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
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
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
        for test_result in report.get("testResults", []):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_vitest_runner.py -v -m ""`
Expected: PASS, all 5 tests green. The three `@pytest.mark.slow` tests perform a real `npm install` — confirm the exact exit codes and JSON shapes empirically against this run rather than assuming they match Task 1's pytest numbers, per this project's established "verify exit codes per tool" discipline.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/vitest_runner.py radar-audit/tests/test_vitest_runner.py
git commit -m "feat(radar-audit): add VitestRunner for criterion 3.1 (JavaScript)"
```

---

### Task 3: `PestRunner` (criterion 3.1, PHP)

**Files:**
- Create: `src/radar_audit/runners/pest_runner.py`
- Test: `tests/test_pest_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner`.
- Produces: `PestRunner` with `tool_name="pest"`, `scope="subproject"`, `supported_stacks=frozenset({"php"})`. Same `raw_output` shape as Tasks 1-2.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pest_runner.py
import subprocess

import pytest
from radar_audit.runners.pest_runner import PestRunner

from tests.git_helpers import init_git_repo

_PHPUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
>
    <testsuites>
        <testsuite name="Test Suite">
            <directory suffix="Test.php">./tests</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>src</directory>
        </include>
    </source>
</phpunit>
"""

_CALCULATOR_PHP = """<?php

class Calculator
{
    public function add(int $a, int $b): int
    {
        return $a + $b;
    }
}
"""


def _install_local_pest(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"pestphp/pest": "^3.0"}, '
        '"config": {"allow-plugins": {"pestphp/pest-plugin": true}}}\n'
    )
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_pass_and_coverage_on_passing_suite(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(3);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


@pytest.mark.slow
def test_reports_failures_with_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(4);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "tests/Unit/CalculatorTest.php"


@pytest.mark.slow
def test_reports_zero_collected_as_no_tests(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"phpunit.xml": _PHPUNIT_XML, "src/Calculator.php": _CALCULATOR_PHP},
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 0


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/Calculator.php": "<?php\n"})

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PestRunner()

    assert runner.tool_name == "pest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pest_runner.py -v -m ""`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pest_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/pest_runner.py
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

            if not junit_path.exists():
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )

            raw_output = self._parse_junit(junit_path)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_pest_runner.py -v -m ""`
Expected: PASS, all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pest_runner.py radar-audit/tests/test_pest_runner.py
git commit -m "feat(radar-audit): add PestRunner for criterion 3.1 (PHP)"
```

---

### Task 4: `normalize_unit_test_pass_rate` (criterion 3.1 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/unit_test_pass_rate.py`
- Test: `tests/test_normalize_unit_test_pass_rate.py`

**Interfaces:**
- Consumes: `ToolResult` rows with `tool_name` in `{"pytest-cov", "vitest", "pest"}`, shaped per Tasks 1-3. `get_or_create_scoring_run`/`get_criterion` from `radar_audit.normalizers.shared` (existing).
- Produces: `normalize_unit_test_pass_rate(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_unit_test_pass_rate.py
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.unit_test_pass_rate import normalize_unit_test_pass_rate
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Testing & reliability",
        "Unit tests present & passing, with coverage",
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_all_tests_pass(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 3, "passed": 3, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": 90.0,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_sums_ratio_across_subprojects_and_adds_finding_for_failures(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 2, "passed": 1, "failed": 1, "skipped": 0},
            "failures": [{"file": "tests/test_a.py", "name": "test_a", "line": None}],
            "coverage_percent": 40.0,
        },
        exit_code=1,
        duration_ms=10,
    )
    frontend = ToolResult(
        audit_id=audit.id,
        tool_name="vitest",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={
            "tests": {"total": 2, "passed": 2, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": 95.0,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(backend)
    db_session.add(frontend)
    db_session.commit()

    score = normalize_unit_test_pass_rate(
        db_session, scoring_run, criterion, [backend, frontend]
    )

    assert score is not None
    assert score.value == 7.5  # (1 + 2) / (2 + 2) * 10

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    descriptions = [f.description for f in findings]
    assert any("Failing test" in d for d in descriptions)
    assert any("below the 50.0% floor" in d for d in descriptions)


def test_returns_none_when_zero_tests_collected(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": None,
        },
        exit_code=5,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_unit_test_pass_rate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.unit_test_pass_rate'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/unit_test_pass_rate.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# pytest-cov's exit code 5 ("no tests collected") is still a usable, successful run --
# its tests.total is naturally 0 and contributes nothing to the summed ratio. exit 127
# (binary/tool missing) is excluded from all three.
_USABLE_EXIT_CODES_BY_TOOL = {
    "pytest-cov": {0, 1, 5},
    "vitest": {0, 1},
    "pest": {0, 1},
}
_RELEVANT_TOOLS = set(_USABLE_EXIT_CODES_BY_TOOL)
# Fixed floor (not a scored band) per spec §3.1's design decision to keep coverage
# out of the score arithmetic entirely -- informational only.
_COVERAGE_FLOOR = 50.0


def normalize_unit_test_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL.get(r.tool_name, set())
    ]
    if not relevant:
        return None

    passed = 0
    collected = 0
    for tool_result in relevant:
        tests = tool_result.raw_output.get("tests", {})
        passed += tests.get("passed", 0)
        collected += tests.get("total", 0)

        for failure in tool_result.raw_output.get("failures", []):
            _add_failure_finding(session, scoring_run, criterion, tool_result, failure)

        coverage_percent = tool_result.raw_output.get("coverage_percent")
        if coverage_percent is not None and coverage_percent < _COVERAGE_FLOOR:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.LOW,
                    description=(
                        f"Coverage is {coverage_percent}%, below the {_COVERAGE_FLOOR}% floor"
                    ),
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

    if collected == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(passed / collected) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _add_failure_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    failure: dict[str, object],
) -> None:
    name = failure.get("name") or "unknown test"
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=f"Failing test: {name}",
            file=failure.get("file"),
            line=failure.get("line"),
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_unit_test_pass_rate.py -v`
Expected: PASS, all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py radar-audit/tests/test_normalize_unit_test_pass_rate.py
git commit -m "feat(radar-audit): add normalize_unit_test_pass_rate for criterion 3.1"
```

---

### Task 5: `IntegrationTestRunner` (criterion 3.2, repo-scope)

**Files:**
- Create: `src/radar_audit/runners/integration_test_runner.py`
- Test: `tests/test_integration_test_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner`.
- Produces: `IntegrationTestRunner` with `tool_name="integration-test-heuristic"`, `scope="repo"`, `supported_stacks=frozenset({"python", "javascript", "php"})`. `raw_output` shape: `{"total_test_files": int, "integration_test_files": int, "files": [{"path": str, "is_integration": bool}]}`. Task 6 consumes this shape.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_integration_test_runner.py
from radar_audit.runners.integration_test_runner import IntegrationTestRunner

from tests.git_helpers import init_git_repo


def test_classifies_python_by_directory_name(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_unit.py": "def test_unit():\n    assert True\n",
            "tests/integration/test_flow.py": "def test_flow():\n    assert True\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_python_by_pytest_marker(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_unit.py": "def test_unit():\n    assert True\n",
            "tests/test_flow.py": (
                "import pytest\n\n\n"
                "@pytest.mark.integration\n"
                "def test_flow():\n    assert True\n"
            ),
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_javascript_by_integration_naming(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.test.js": "test('adds', () => {});\n",
            "src/flow.integration.test.js": "test('flow', () => {});\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_php_feature_vs_unit_by_pest_convention(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/Unit/CalculatorTest.php": "<?php\n",
            "tests/Feature/FlowTest.php": "<?php\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_reports_zero_when_no_test_files_exist(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.py": "def add(a, b):\n    return a + b\n"})

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 0
    assert result.raw_output["integration_test_files"] == 0


def test_reports_tool_identity():
    runner = IntegrationTestRunner()

    assert runner.tool_name == "integration-test-heuristic"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset({"python", "javascript", "php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_integration_test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.integration_test_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/integration_test_runner.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class IntegrationTestRunner:
    """Cross-stack filesystem heuristic classifying test files as integration or unit
    (criterion 3.2). No tool produces this signal directly -- see design spec §3.
    Runs once per repo (scope="repo"): a monorepo's Python/JS/PHP integration ratios
    are combined into one repo-wide figure.
    """

    tool_name = "integration-test-heuristic"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python", "javascript", "php"})
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        files: list[dict[str, object]] = []
        for file_path in sorted(target_path.rglob("*")):
            if not file_path.is_file():
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            classification = self._classify(file_path)
            if classification is None:
                continue
            files.append(
                {
                    "path": str(file_path.relative_to(target_path)),
                    "is_integration": classification,
                }
            )

        total = len(files)
        integration = sum(1 for f in files if f["is_integration"])

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"integration-test-walk {target_path}",
            raw_output={
                "total_test_files": total,
                "integration_test_files": integration,
                "files": files,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _classify(self, file_path: Path) -> bool | None:
        parts = file_path.parts
        name = file_path.name
        suffix = file_path.suffix

        if suffix == ".py":
            if not (name.startswith("test_") or name.endswith("_test.py")):
                return None
            if "integration" in parts:
                return True
            try:
                content = file_path.read_text(errors="ignore")
            except OSError:
                content = ""
            return "@pytest.mark.integration" in content

        if suffix in {".js", ".ts", ".jsx", ".tsx"}:
            stem = file_path.stem
            if ".test" not in stem and ".spec" not in stem:
                return None
            if "integration" in parts:
                return True
            return ".integration.test" in name or ".integration.spec" in name

        if suffix == ".php":
            if not name.endswith("Test.php"):
                return None
            if "tests" not in {p.lower() for p in parts}:
                return None
            return "Feature" in parts

        return None

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(
            excluded == file_path or excluded in file_path.parents for excluded in exclude_paths
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_integration_test_runner.py -v`
Expected: PASS, all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/integration_test_runner.py radar-audit/tests/test_integration_test_runner.py
git commit -m "feat(radar-audit): add IntegrationTestRunner for criterion 3.2"
```

---

### Task 6: `normalize_integration_tests` (criterion 3.2 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/integration_tests.py`
- Test: `tests/test_normalize_integration_tests.py`

**Interfaces:**
- Consumes: `ToolResult` rows with `tool_name == "integration-test-heuristic"`, shaped per Task 5.
- Produces: `normalize_integration_tests(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_integration_tests.py
from radar_audit.normalizers.integration_tests import normalize_integration_tests
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Testing & reliability", "Integration tests"
    )
    return audit, scoring_run, criterion


def _tool_result(audit_id, total, integration):
    return ToolResult(
        audit_id=audit_id,
        tool_name="integration-test-heuristic",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "total_test_files": total,
            "integration_test_files": integration,
            "files": [],
        },
        exit_code=0,
        duration_ms=10,
    )


def test_scores_ten_when_ratio_above_50_percent(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=10, integration=6)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_zero_when_no_integration_tests_present(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=5, integration=0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0


def test_returns_none_when_no_test_files_at_all(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=0, integration=0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_integration_tests(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_integration_tests.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.integration_tests'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/integration_tests.py
from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_integration_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.tool_name == "integration-test-heuristic" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    total = tool_result.raw_output.get("total_test_files", 0)
    if total == 0:
        # No tests at all is already carried by criterion 3.1 -- not penalized twice.
        return None

    integration = tool_result.raw_output.get("integration_test_files", 0)
    ratio_percent = (integration / total) * 100

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(ratio_percent),
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(ratio_percent: float) -> float:
    # Bands: 0%->0, 0-10%->4, 10-25%->6, 25-50%->8, >50%->10 (spec §3.4). Resolved
    # during design but provisional -- not yet calibrated against real portfolio data
    # (spec §11), same discipline as every prior increment's thresholds.
    if ratio_percent <= 0.0:
        return 0.0
    if ratio_percent <= 10.0:
        return 4.0
    if ratio_percent <= 25.0:
        return 6.0
    if ratio_percent <= 50.0:
        return 8.0
    return 10.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_integration_tests.py -v`
Expected: PASS, all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/integration_tests.py radar-audit/tests/test_normalize_integration_tests.py
git commit -m "feat(radar-audit): add normalize_integration_tests for criterion 3.2"
```

---

### Task 7: `CiWorkflowRunner` (criteria 3.3 + 3.4, repo-scope)

**Files:**
- Create: `src/radar_audit/runners/ci_workflow_runner.py`
- Test: `tests/test_ci_workflow_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner`; PyYAML (already a project dependency).
- Produces: `CiWorkflowRunner` with `tool_name="ci-workflow"`, `scope="repo"`, `supported_stacks=frozenset()`. `raw_output` shape: `{"workflows_found": int, "test_execution_found": bool, "playwright_execution_found": bool}`. Tasks 9 and 10 both consume this shape.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ci_workflow_runner.py
from radar_audit.runners.ci_workflow_runner import CiWorkflowRunner

from tests.git_helpers import init_git_repo

_TEST_WORKFLOW = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest
"""

_PLAYWRIGHT_WORKFLOW = """name: E2E
on: [push]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx playwright test
"""

_UNRELATED_WORKFLOW = """name: Lint
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx eslint .
"""


def test_detects_test_execution(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _TEST_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["workflows_found"] == 1
    assert result.raw_output["test_execution_found"] is True
    assert result.raw_output["playwright_execution_found"] is False


def test_detects_playwright_execution(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/e2e.yml": _PLAYWRIGHT_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is False
    assert result.raw_output["playwright_execution_found"] is True


def test_reports_both_false_for_unrelated_workflow(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/lint.yml": _UNRELATED_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is False
    assert result.raw_output["playwright_execution_found"] is False


def test_reports_zero_workflows_when_directory_absent(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "# fixture\n"})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["workflows_found"] == 0
    assert result.raw_output["test_execution_found"] is False


def test_reports_tool_identity():
    runner = CiWorkflowRunner()

    assert runner.tool_name == "ci-workflow"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_ci_workflow_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.ci_workflow_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/ci_workflow_runner.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import yaml

from radar_audit.runner import RawToolOutput

_TEST_KEYWORDS = ("pytest", "vitest", "npm test", "pnpm test", "pest", "phpunit")
_PLAYWRIGHT_KEYWORDS = ("playwright test", "npx playwright test")


class CiWorkflowRunner:
    """Parses .github/workflows/*.yml directly with PyYAML for test-invocation and
    Playwright keywords, feeding both criterion 3.3 (E2E) and 3.4 (CI test execution)
    from a single pass -- spec §6. No subprocess, always exit_code 0: presence/absence
    is encoded in raw_output, not in the runner's own success/failure.
    """

    tool_name = "ci-workflow"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        workflows_dir = target_path / ".github" / "workflows"
        workflow_files: list[Path] = []
        if workflows_dir.is_dir():
            workflow_files = sorted(
                p for p in workflows_dir.iterdir() if p.suffix in {".yml", ".yaml"} and p.is_file()
            )

        test_execution_found = False
        playwright_execution_found = False
        for workflow_file in workflow_files:
            for run_value in self._run_steps(workflow_file):
                lowered = run_value.lower()
                if any(keyword in lowered for keyword in _TEST_KEYWORDS):
                    test_execution_found = True
                if any(keyword in lowered for keyword in _PLAYWRIGHT_KEYWORDS):
                    playwright_execution_found = True

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"ci-workflow-parse {workflows_dir}",
            raw_output={
                "workflows_found": len(workflow_files),
                "test_execution_found": test_execution_found,
                "playwright_execution_found": playwright_execution_found,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _run_steps(self, workflow_file: Path) -> list[str]:
        try:
            content = yaml.safe_load(workflow_file.read_text(errors="ignore"))
        except yaml.YAMLError:
            return []
        if not isinstance(content, dict):
            return []

        jobs = content.get("jobs", {})
        if not isinstance(jobs, dict):
            return []

        run_values: list[str] = []
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps", [])
            if not isinstance(steps, list):
                continue
            for step in steps:
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    run_values.append(step["run"])
        return run_values
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_ci_workflow_runner.py -v`
Expected: PASS, all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/ci_workflow_runner.py radar-audit/tests/test_ci_workflow_runner.py
git commit -m "feat(radar-audit): add CiWorkflowRunner for criteria 3.3 and 3.4"
```

---

### Task 8: `PlaywrightPresenceRunner` (criterion 3.3, subproject-scope)

**Files:**
- Create: `src/radar_audit/runners/playwright_presence_runner.py`
- Test: `tests/test_playwright_presence_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput` from `radar_audit.runner`.
- Produces: `PlaywrightPresenceRunner` with `tool_name="playwright-presence"`, `scope="subproject"`, `supported_stacks=frozenset({"javascript"})`. `raw_output` shape: `{"present": bool}`. Task 9 consumes this shape.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_playwright_presence_runner.py
from radar_audit.runners.playwright_presence_runner import PlaywrightPresenceRunner

from tests.git_helpers import init_git_repo


def test_detects_presence_via_config_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"playwright.config.ts": "export default {};\n", "package.json": "{}\n"},
    )

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is True


def test_detects_presence_via_devdependency_only(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": (
                '{"name": "fixture", "devDependencies": {"@playwright/test": "^1.40.0"}}\n'
            )
        },
    )

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is True


def test_reports_absent_when_neither_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"package.json": '{"name": "fixture"}\n'})

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is False


def test_reports_tool_identity():
    runner = PlaywrightPresenceRunner()

    assert runner.tool_name == "playwright-presence"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_playwright_presence_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.playwright_presence_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/playwright_presence_runner.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_CONFIG_FILENAMES = ("playwright.config.js", "playwright.config.ts")


class PlaywrightPresenceRunner:
    """Detects Playwright E2E test setup via config file or devDependency presence
    (criterion 3.3, JavaScript). No subprocess -- spec §6.
    """

    tool_name = "playwright-presence"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        present = any((target_path / filename).exists() for filename in _CONFIG_FILENAMES)
        if not present:
            present = self._has_devdependency(target_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"playwright-presence-check {target_path}",
            raw_output={"present": present},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _has_devdependency(self, target_path: Path) -> bool:
        package_json = target_path / "package.json"
        if not package_json.exists():
            return False
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return False
        return "@playwright/test" in data.get("devDependencies", {})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_playwright_presence_runner.py -v`
Expected: PASS, all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/playwright_presence_runner.py radar-audit/tests/test_playwright_presence_runner.py
git commit -m "feat(radar-audit): add PlaywrightPresenceRunner for criterion 3.3"
```

---

### Task 9: `normalize_e2e_tests` (criterion 3.3 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/e2e_tests.py`
- Test: `tests/test_normalize_e2e_tests.py`

**Interfaces:**
- Consumes: `ToolResult` rows with `tool_name in {"playwright-presence", "ci-workflow"}`, shaped per Tasks 7-8.
- Produces: `normalize_e2e_tests(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_e2e_tests.py
from radar_audit.normalizers.e2e_tests import normalize_e2e_tests
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Testing & reliability", "E2E tests"
    )
    return audit, scoring_run, criterion


def _playwright_result(audit_id, present, subproject_path="frontend"):
    return ToolResult(
        audit_id=audit_id,
        tool_name="playwright-presence",
        tool_version="1.0.0",
        subproject_path=subproject_path,
        command="stub",
        raw_output={"present": present},
        exit_code=0,
        duration_ms=10,
    )


def _ci_result(audit_id, playwright_execution_found):
    return ToolResult(
        audit_id=audit_id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 1,
            "test_execution_found": True,
            "playwright_execution_found": playwright_execution_found,
        },
        exit_code=0,
        duration_ms=10,
    )


def test_scores_done_when_present_and_wired_into_ci(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=True)
    ci_result = _ci_result(audit.id, playwright_execution_found=True)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(
        db_session, scoring_run, criterion, [playwright_result, ci_result]
    )

    assert score is not None
    assert score.value == 10.0


def test_scores_in_progress_when_present_but_not_wired(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=True)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(
        db_session, scoring_run, criterion, [playwright_result, ci_result]
    )

    assert score is not None
    assert score.value == 5.0


def test_scores_todo_when_absent(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=False)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(
        db_session, scoring_run, criterion, [playwright_result, ci_result]
    )

    assert score is not None
    assert score.value == 0.0


def test_returns_none_when_no_javascript_subproject(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(db_session, scoring_run, criterion, [ci_result])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_e2e_tests.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.e2e_tests'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/e2e_tests.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_TODO, _IN_PROGRESS, _DONE = 0, 1, 2
_VALUE_BY_STATUS = {_TODO: 0.0, _IN_PROGRESS: 5.0, _DONE: 10.0}


def normalize_e2e_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    playwright_results = [
        r for r in tool_results if r.tool_name == "playwright-presence" and r.exit_code == 0
    ]
    if not playwright_results:
        # No javascript sub-project ran PlaywrightPresenceRunner at all -> N/A.
        return None

    ci_results = [r for r in tool_results if r.tool_name == "ci-workflow" and r.exit_code == 0]
    ci_wired = bool(
        ci_results and ci_results[0].raw_output.get("playwright_execution_found", False)
    )

    # Worst-status-wins across every javascript sub-project (spec §7).
    worst_status = min(
        _status_for(bool(r.raw_output.get("present", False)), ci_wired) for r in playwright_results
    )

    if worst_status == _TODO:
        _add_finding(
            session,
            scoring_run,
            criterion,
            playwright_results[0],
            FindingSeverity.MEDIUM,
            "Repo is web-facing but has no Playwright E2E test setup",
        )
    elif worst_status == _IN_PROGRESS:
        _add_finding(
            session,
            scoring_run,
            criterion,
            playwright_results[0],
            FindingSeverity.LOW,
            "Playwright is present but not wired into any CI workflow",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_VALUE_BY_STATUS[worst_status],
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _status_for(present: bool, ci_wired: bool) -> int:
    if not present:
        return _TODO
    return _DONE if ci_wired else _IN_PROGRESS


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    severity: FindingSeverity,
    description: str,
) -> None:
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=severity,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_e2e_tests.py -v`
Expected: PASS, all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/e2e_tests.py radar-audit/tests/test_normalize_e2e_tests.py
git commit -m "feat(radar-audit): add normalize_e2e_tests for criterion 3.3"
```

---

### Task 10: `normalize_ci_test_execution` (criterion 3.4 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/ci_test_execution.py`
- Test: `tests/test_normalize_ci_test_execution.py`

**Interfaces:**
- Consumes: `ToolResult` rows with `tool_name == "ci-workflow"`, shaped per Task 7.
- Produces: `normalize_ci_test_execution(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_ci_test_execution.py
from radar_audit.normalizers.ci_test_execution import normalize_ci_test_execution
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Testing & reliability", "CI executes the test suite"
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_test_execution_found(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 1,
            "test_execution_found": True,
            "playwright_execution_found": False,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_zero_and_adds_finding_when_no_ci_runs_tests(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 0,
            "test_execution_found": False,
            "playwright_execution_found": False,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_ci_test_execution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.ci_test_execution'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/ci_test_execution.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_ci_test_execution(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "ci-workflow" and r.exit_code == 0]
    if not relevant:
        return None

    tool_result = relevant[0]
    test_execution_found = bool(tool_result.raw_output.get("test_execution_found", False))

    if not test_execution_found:
        # Total absence of CI test execution is always a real gap (never N/A) --
        # unlike 3.3, nothing structurally prevents any repo from having CI.
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.MEDIUM,
                description="No CI workflow invokes any test command",
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=10.0 if test_execution_found else 0.0,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_ci_test_execution.py -v`
Expected: PASS, all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/ci_test_execution.py radar-audit/tests/test_normalize_ci_test_execution.py
git commit -m "feat(radar-audit): add normalize_ci_test_execution for criterion 3.4"
```

---

### Task 11: Register category-3 runners and validate against a real portfolio repository

**Files:**
- Modify: `src/radar_audit/cli.py` — add the 6 new runner instances to `DEFAULT_RUNNERS`.
- Modify: none else expected beyond fixes surfaced by the real run — mirrors category 2's Task 17.
- Test: none new — existing suites must stay green.

**Interfaces:**
- Consumes: every runner and normalizer from Tasks 1-10, the existing `radar-audit run` CLI, and `radar_audit.orchestrator`'s discovery/dispatch machinery (unchanged).
- Produces: a clean, meaningful `ScoringRun` with up to 4 category-3 `Score`s (or well-justified `None`s where a criterion is genuinely N/A for that repo) against a real portfolio repository, and any runner/normalizer fixes required to get there.

- [ ] **Step 1: Register the 6 new runners for dispatch**

In `src/radar_audit/cli.py`, add the imports and instances for `PytestCoverageRunner`, `VitestRunner`, `PestRunner`, `IntegrationTestRunner`, `CiWorkflowRunner`, `PlaywrightPresenceRunner` to `DEFAULT_RUNNERS`, following the exact same pattern already used for the category-2 runners:

```python
from radar_audit.runners.ci_workflow_runner import CiWorkflowRunner
from radar_audit.runners.integration_test_runner import IntegrationTestRunner
from radar_audit.runners.pest_runner import PestRunner
from radar_audit.runners.playwright_presence_runner import PlaywrightPresenceRunner
from radar_audit.runners.pytest_coverage_runner import PytestCoverageRunner
from radar_audit.runners.vitest_runner import VitestRunner
```

```python
DEFAULT_RUNNERS: list[ToolRunner] = [
    # ... existing category 1/2 runners unchanged ...
    PytestCoverageRunner(),
    VitestRunner(),
    PestRunner(),
    IntegrationTestRunner(),
    CiWorkflowRunner(),
    PlaywrightPresenceRunner(),
]
```

- [ ] **Step 2: Run the full existing test suite**

Run: `cd radar-audit && uv run pytest -v -m ""`
Expected: PASS, all tests from Tasks 1-10 plus every pre-existing 2.0/2.1/2.2 test green.

- [ ] **Step 3: Run a real audit against a portfolio repository**

Pick a real portfolio repo already used for 2.1's and 2.2's own validation (Summit-Stats — PHP/Laravel + Vue — or GeoChallenge-Tracker — Python/FastAPI + Vue). Run:

```bash
cd radar-audit && uv run radar-audit run <repo-name>
```

Then run the four category-3 normalizers against the resulting `ToolResult`s (reuse the same manual-normalizer-invocation approach used for 2.1's and 2.2's own validation, since CLI wiring to normalizers is still out of scope per `project_radar_audit_phase4.md`'s open item) and inspect the resulting `Score`/`Finding` rows for each.

- [ ] **Step 4: Fix whatever the real run surfaces**

Common classes of gaps to expect, based on 2.1's and 2.2's own real-world validation history: additional vendor/build directories not covered by `_SKIP_DIRNAMES`, a real repo's `requirements.txt`/`package.json`/`composer.json` shape triggering an edge case Tasks 1-10's fixtures didn't cover (e.g. a monorepo's actual test-file naming conventions not matching the 3.2 heuristics exactly, a real `.github/workflows/*.yml` using a matrix strategy or a composite action instead of a plain `run:` step, Pest's actual coverage driver requiring Xdebug/PCOV to be installed on the target rather than assumed present). Fix each in the relevant runner/normalizer, add a regression test capturing the real-world shape that was missed, and commit each fix separately with a `fix(radar-audit): <specific bug>` message.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(radar-audit): register category 3 runners and validate against a real portfolio repo"
```
