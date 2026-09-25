# PytestCoverageRunner Crash Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix criterion 3.1 (unit tests + coverage) silently scoring 10.0/10 on repos whose Python test suite crashes entirely: `PytestCoverageRunner` must install `requirements-dev.txt` (test-only dependencies) alongside `requirements.txt`, and `unit_test_pass_rate.py` must not drop a crashed pytest run from the scoring ratio when its `junit.xml` still carries real, usable data.

**Architecture:** Two independent, additive changes to existing code, no new files. `PytestCoverageRunner.run()` gains a second `--with-requirements` flag (uvx supports repeating the flag to combine multiple requirement files) when `requirements-dev.txt` exists alongside `requirements.txt`. `normalize_unit_test_pass_rate()`'s relevance filter is widened from a pure exit-code allowlist to also admit any tool result whose `raw_output["tests"]["total"] > 0` regardless of exit code (real junit data is trustworthy on its own), and rescued (abnormal-exit-code) results now also raise a distinct `HIGH`-severity `Finding` alongside the existing per-test-failure findings.

**Tech Stack:** Python 3, pytest, `uvx` (ephemeral tool execution), SQLModel.

**Spec:** `docs/work-in-progress/report-review-findings.md`, finding #10, in the main checkout (this file is gitignored scratch and not present in this worktree - its relevant content is reproduced below so this plan is self-contained):

> ## 10. Criterion 3.1 scores 10.0/10 while the Python test suite is 100% broken: `PytestCoverageRunner` never installs test-only dependencies, and `unit_test_pass_rate.py` silently drops the resulting crashed run instead of scoring it
>
> - **Files:** `radar-audit/src/radar_audit/runners/pytest_coverage_runner.py` (`run`, the `uvx --with pytest-cov --with-requirements requirements.txt` command construction), `radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py` (`_USABLE_EXIT_CODES_BY_TOOL["pytest-cov"] = {0, 1, 5}`).
> - **Confirmed via manual reproduction** (GeoChallenge-Tracker, user-run, 2026-09-24) and cross-checked against the live DB.
> - **Root cause, two compounding bugs:**
>   1. `PytestCoverageRunner` only installs the project's `requirements.txt` (production dependencies) plus `pytest-cov`. It never installs `requirements-dev.txt`, which is where this project declares its actual test toolchain: `pytest`, `pytest-asyncio`, `pytest-env`, `pytest-mock`. Confirmed this is the intended split by reading the project's own `.github/workflows/ci.yml`, which always runs `pip install -r backend/requirements.txt` **and** `pip install -r backend/requirements-dev.txt` before invoking pytest. Without `pytest-env`, the project's `pytest.ini` directive `env = ENV_FILE=../.env` (meant to point Pydantic Settings at the repo-root `.env`) has no effect, since the plugin that implements the `env` ini option is absent. `app/core/settings.py`'s `_resolve_env_file()` then falls back to its default, `backend/.env`, which does not carry the same values as the intended `../.env`. `Settings()` (instantiated at import time by `app/db/mongodb.py`) then raises a Pydantic `ValidationError` for 20 missing required fields, which crashes collection for every test that transitively imports `app.main`/`app.db.mongodb`/`app.core.security`: 58 collection errors out of 58 total tests, exit code 2.
>   2. `unit_test_pass_rate.py` only treats `pytest-cov` exit codes `{0, 1, 5}` as usable; exit code 2 is filtered out of `relevant` entirely, so this crashed run contributes **nothing** to the pooled ratio, not even as a penalty. This happens despite the run producing a fully valid, informative `junit.xml` (`total: 58, passed: 0, failed: 58`, confirmed present in `tool_result` id 80's `raw_output`), which the normalizer never even looks at once the exit-code gate excludes it.
> - **Confirmed via the live DB:** `tool_result` id 80 (`pytest-cov`): `exit_code=2`, `{"tests": {"total": 58, "passed": 0, "failed": 58, "skipped": 0}, ...}`. `tool_result` id 66 (`vitest`): `exit_code=0`, `{"tests": {"total": 407, "passed": 407, "failed": 0, "skipped": 0}, "coverage_percent": 25.6}`. Because pytest-cov is excluded, the normalizer computes `passed=407, collected=407` (vitest alone) -> `407/407 x 10 = 10.0/10`, exactly matching the report.
> - **Impact:** critical, and arguably the most severe finding of this review. A repo whose entire Python test suite cannot run at all gets a perfect 10.0/10 on this criterion as long as its JS suite is healthy, because the broken side is dropped rather than counted as a failure. Any mixed-stack repo where one language's test run crashes for an environment reason (missing dependency, missing config, wrong cwd) rather than a genuine test failure is exposed to the same silent masking.
> - **Suggested fix:** two independent, both needed:
>   1. `PytestCoverageRunner` should also install `requirements-dev.txt` when present (mirroring the project's own CI), the same category of fix as finding #1's `mypy --with-requirements`.
>   2. `unit_test_pass_rate.py` should not silently drop exit code 2 (or any exit code) when the tool still produced usable `junit.xml` data (`tests.total > 0`). At minimum, a crashed run with real collected failures should count against the ratio rather than being excluded; ideally, a fully-crashed suite should also raise a high-severity `Finding` distinct from ordinary failing-test findings, since "0/58 collected" is a materially different signal than "3/58 tests failed."
> - **Status:** dispositioned 2026-09-24: fix now, Phase 3, both sub-fixes needed. Most severe finding in this review.

## Global Constraints

- Keep `PytestCoverageRunner`'s class name, file name, `tool_name = "pytest-cov"`, and `RawToolOutput` contract (`command`, `raw_output`, `exit_code`, `duration_ms`) unchanged. This is a targeted fix to the command construction only.
- `uvx` accepts `--with-requirements` more than once to combine multiple requirement files into the same ephemeral environment - empirically verified this session (`uvx --with-requirements requirements.txt --with-requirements requirements-dev.txt python -c "import requests, pytest"` installs and imports both). Use two separate `--with-requirements` flags, one per file, never merge the files' contents into one temp file.
- `_USABLE_EXIT_CODES_BY_TOOL` in `unit_test_pass_rate.py` stays exactly as `{"pytest-cov": {0, 1, 5}, "vitest": {0, 1}, "pest": {0, 1}}` - it still names the *normal* exit codes that need no extra finding. The fix adds a second, independent admission path (`tests.total > 0`) rather than changing this dict's values, and applies identically regardless of which of the three tools produced the abnormal exit code (not a pytest-cov-only special case), since vitest/pest could hit the same class of bug.
- The new abnormal-exit `Finding` uses `FindingSeverity.HIGH` (imported already; no new import needed) and is added once per rescued `tool_result`, in addition to (not instead of) the existing per-failing-test `Finding`s that `_add_failure_finding` already creates from that same tool result's `failures` list.
- Do not touch `PytestCoverageRunner`'s coverage parsing, junit parsing, or timeout/error-fallback branches (lines 44-84 of `pytest_coverage_runner.py` outside the `command` list construction) - out of scope for this fix.
- `requirements-dev.txt` is looked up the same way as `requirements.txt` already is: `target_path / "requirements-dev.txt"`, existence-checked, no assumption about its contents.

## Review Focus

- **A crashed run whose `junit.xml` still carries zero collected tests** (e.g. a tool binary missing entirely, or a crash before pytest even starts collecting) - must NOT be rescued into the ratio; the existing exclude-and-contribute-nothing behavior for genuinely empty/unusable results must be preserved. Covered by Task 2's `test_still_excludes_a_crashed_run_that_produced_no_usable_junit_data`.
- **A rescued crashed run pooled together with a healthy run from a different tool** (the real-world scenario: pytest-cov crashed at 58/58, vitest healthy at 407/407) - the ratio must pool both, not let the crash either zero out the whole score or get silently ignored. Covered by Task 2's `test_rescues_a_crashed_pytest_run_and_pools_it_with_a_healthy_vitest_run`.
- **A repo with `requirements.txt` but no `requirements-dev.txt`** - must keep working exactly as before (single `--with-requirements` flag), not error out on a missing optional file. Already covered by the existing, unmodified `test_reports_full_pass_and_coverage` (no `requirements-dev.txt` is ever created in that test's fixture).
- **The existing failing-test `Finding`s for a rescued run's individual failures** - must still be created exactly as before; the new abnormal-exit `Finding` is additive, not a replacement. Covered by Task 2's `test_rescues_a_crashed_pytest_run_and_pools_it_with_a_healthy_vitest_run`, which asserts both finding kinds are present.

---

### Task 1: `PytestCoverageRunner` installs `requirements-dev.txt` when present

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/pytest_coverage_runner.py:30-34`
- Test: `radar-audit/tests/test_pytest_coverage_runner.py`

**Interfaces:**
- Consumes: nothing new - `target_path: Path` is already the method's parameter.
- Produces: no new public interface; `run()`'s existing `RawToolOutput` contract is unchanged. Task 2 does not depend on this task's change.

- [ ] **Step 1: Write the failing test**

Open `radar-audit/tests/test_pytest_coverage_runner.py` and add this test function, after `test_reports_full_pass_and_coverage`:

```python
def test_installs_requirements_dev_txt_when_present(tmp_path):
    # requirements-dev.txt declares pytest-env, which implements the "env"
    # pytest.ini option used below. Without it, pytest emits a
    # PytestConfigWarning for the unrecognized "env" key and never sets
    # FOO, so the test fails with a KeyError; with it installed, FOO is set
    # before the test runs and it passes. This mirrors finding #10's real
    # scenario, where a project's pytest.ini "env" directive silently had
    # no effect because pytest-env was declared only in requirements-dev.txt.
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "requirements-dev.txt": "pytest-env\n",
            "pytest.ini": "[pytest]\nenv =\n    FOO=bar\n",
            "tests/test_env.py": (
                "import os\n\n\n"
                "def test_reads_env_var_set_by_pytest_env_plugin():\n"
                "    assert os.environ['FOO'] == 'bar'\n"
            ),
        },
    )

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 1
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_pytest_coverage_runner.py::test_installs_requirements_dev_txt_when_present -v`
Expected: FAIL - `assert result.exit_code == 0` fails because `exit_code` is `1` (pytest-env isn't installed, `FOO` is never set, `os.environ['FOO']` raises `KeyError`, the test is reported as 1 failed).

- [ ] **Step 3: Install `requirements-dev.txt` in the command construction**

In `radar-audit/src/radar_audit/runners/pytest_coverage_runner.py`, replace:

```python
            command = ["uvx", "--with", "pytest-cov"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            command.append("pytest")
```

with:

```python
            command = ["uvx", "--with", "pytest-cov"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            requirements_dev = target_path / "requirements-dev.txt"
            if requirements_dev.exists():
                command.extend(["--with-requirements", str(requirements_dev)])
            command.append("pytest")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_pytest_coverage_runner.py::test_installs_requirements_dev_txt_when_present -v`
Expected: PASS - `pytest-env` is now installed, `FOO` is set before the test body runs, `exit_code == 0`, `passed == 1`.

- [ ] **Step 5: Run the full existing file to confirm no regressions**

Run: `cd radar-audit && uv run pytest tests/test_pytest_coverage_runner.py -v`
Expected: PASS - all 6 tests (5 existing + the new one) pass. `test_reports_full_pass_and_coverage` in particular confirms the no-`requirements-dev.txt` path still works unchanged.

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pytest_coverage_runner.py radar-audit/tests/test_pytest_coverage_runner.py
git commit -m "fix(radar-audit): install requirements-dev.txt in PytestCoverageRunner

Modified files:
- radar-audit/src/radar_audit/runners/pytest_coverage_runner.py - add a
  second --with-requirements flag for requirements-dev.txt when present
- radar-audit/tests/test_pytest_coverage_runner.py - add
  test_installs_requirements_dev_txt_when_present"
```

---

### Task 2: `unit_test_pass_rate.py` rescues crashed runs with usable `junit.xml` data

**Files:**
- Modify: `radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py`
- Test: `radar-audit/tests/test_normalize_unit_test_pass_rate.py`

**Interfaces:**
- Consumes: `ToolResult.raw_output["tests"]["total"|"passed"]`, `ToolResult.exit_code`, `ToolResult.tool_name` - all already read by the existing function. No new fields.
- Produces: no new public interface; `normalize_unit_test_pass_rate()`'s signature and return type (`Score | None`) are unchanged. The behavior change is purely in which `tool_results` entries are admitted to the ratio and what findings get created.

- [ ] **Step 1: Write the failing tests**

Open `radar-audit/tests/test_normalize_unit_test_pass_rate.py` and add these two test functions, after `test_returns_none_when_zero_tests_collected`:

```python
def test_rescues_a_crashed_pytest_run_and_pools_it_with_a_healthy_vitest_run(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    crashed_backend = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 58, "passed": 0, "failed": 58, "skipped": 0},
            "failures": [{"file": "tests/test_a.py", "name": "test_a", "line": None}],
            "coverage_percent": None,
        },
        exit_code=2,
        duration_ms=10,
    )
    healthy_frontend = ToolResult(
        audit_id=audit.id,
        tool_name="vitest",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={
            "tests": {"total": 407, "passed": 407, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": 95.0,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(crashed_backend)
    db_session.add(healthy_frontend)
    db_session.commit()

    score = normalize_unit_test_pass_rate(
        db_session, scoring_run, criterion, [crashed_backend, healthy_frontend]
    )

    assert score is not None
    assert score.value == pytest.approx((0 + 407) / (58 + 407) * 10)

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    descriptions = [f.description for f in findings]
    assert any("Failing test" in d for d in descriptions)
    crash_findings = [f for f in findings if "exited abnormally" in (f.description or "")]
    assert len(crash_findings) == 1
    assert crash_findings[0].severity == FindingSeverity.HIGH
    assert "exit code 2" in crash_findings[0].description
    assert "58 tests" in crash_findings[0].description


def test_still_excludes_a_crashed_run_that_produced_no_usable_junit_data(db_session):
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
        exit_code=2,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is None
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert findings == []
```

This test file needs two new imports at the top: `import pytest` and `from radar_core.enums import FindingSeverity`. Add both to the existing import block, e.g.:

```python
import pytest
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.unit_test_pass_rate import normalize_unit_test_pass_rate
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import FindingSeverity
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_unit_test_pass_rate.py -v`
Expected: the two new tests FAIL. `test_rescues_a_crashed_pytest_run_and_pools_it_with_a_healthy_vitest_run` fails on `assert score is not None` (the crashed run's exit code 2 is filtered out entirely by the current `_USABLE_EXIT_CODES_BY_TOOL` gate, so only the frontend run pools, giving `score.value == 10.0`, not the pooled ratio - the assertion right after would fail too, whichever pytest reports first). `test_still_excludes_a_crashed_run_that_produced_no_usable_junit_data` PASSES already (this is the preserved-behavior regression test, written now to pin the behavior before it's touched, alongside the new-behavior test). The other 3 existing tests in the file keep passing.

- [ ] **Step 3: Widen the relevance filter and add the abnormal-exit finding**

In `radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py`, replace:

```python
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
```

with:

```python
    relevant = []
    for r in tool_results:
        if r.tool_name not in _RELEVANT_TOOLS:
            continue
        if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL[r.tool_name]:
            relevant.append(r)
        elif r.raw_output.get("tests", {}).get("total", 0) > 0:
            # Crashed or interrupted run (e.g. pytest exit code 2 from
            # collection errors) whose junit.xml still carries real counts --
            # rescue it into the ratio instead of silently dropping the
            # whole suite. The abnormal exit code itself is flagged below.
            relevant.append(r)
    if not relevant:
        return None

    passed = 0
    collected = 0
    for tool_result in relevant:
        tests = tool_result.raw_output.get("tests", {})
        passed += tests.get("passed", 0)
        collected += tests.get("total", 0)

        if tool_result.exit_code not in _USABLE_EXIT_CODES_BY_TOOL[tool_result.tool_name]:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.HIGH,
                    description=(
                        f"{tool_result.tool_name} exited abnormally (exit code "
                        f"{tool_result.exit_code}) while still reporting "
                        f"{tests.get('total', 0)} tests "
                        f"({tests.get('passed', 0)} passed) -- treating as a crashed run"
                    ),
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

        for failure in tool_result.raw_output.get("failures", []):
            _add_failure_finding(session, scoring_run, criterion, tool_result, failure)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_unit_test_pass_rate.py -v`
Expected: PASS - all 6 tests (4 existing + 2 new) pass.

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py radar-audit/tests/test_normalize_unit_test_pass_rate.py
git commit -m "fix(radar-audit): rescue crashed test runs with usable junit data

Modified files:
- radar-audit/src/radar_audit/normalizers/unit_test_pass_rate.py - admit
  tool results with an abnormal exit code into the ratio when their
  junit.xml still reports total > 0, and raise a HIGH-severity finding
  for the abnormal exit code itself
- radar-audit/tests/test_normalize_unit_test_pass_rate.py - add
  test_rescues_a_crashed_pytest_run_and_pools_it_with_a_healthy_vitest_run
  and test_still_excludes_a_crashed_run_that_produced_no_usable_junit_data"
```

---

### Task 3: Full suite verification

**Files:** none modified - verification only.

**Interfaces:** none.

- [ ] **Step 1: Run the full test suite**

Run: `cd radar-audit && uv run pytest -q`
Expected: PASS - 362 passed, 0 failed (baseline 359 confirmed at `main`'s `b1fefa9` this session + 1 new test in Task 1 + 2 new tests in Task 2).

- [ ] **Step 2: Commit the plan document**

```bash
git add docs/superpowers/plans/2026-09-25-radar-audit-pytest-coverage-crash-handling.md
git commit -m "docs: write radar-audit pytest-coverage-crash-handling implementation plan"
```
