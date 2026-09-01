# Radar-audit Category 2 (Code Quality) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 11 real `ToolRunner`s and 5 normalizers covering Quality Framework category 2 ("Code quality"): Linter clean pass rate, Type-checking pass, Cyclomatic complexity, Pre-commit quality gate, Code duplication — across Python, JavaScript/TypeScript, and PHP.

**Architecture:** Same shape as increment 2.1: each criterion gets one or more `ToolRunner` classes (one class per underlying tool, not per stack) producing a `RawToolOutput`, and one normalizer function that reads `ToolResult` rows for the relevant `tool_name`s and writes `Score`/`Finding` rows via the existing `get_or_create_scoring_run`/`get_criterion` helpers. No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration — all infrastructure needed already exists from 2.0/2.1.

**Tech Stack:** Python 3.12, SQLModel, pytest, uv/uvx (Ruff, mypy, radon), npx (ESLint, TypeScript, jscpd), Composer (Pint, PHPStan/Larastan, PHPMD).

**Spec:** `docs/superpowers/specs/2026-08-29-radar-audit-category-2-code-quality-design.md`

## Global Constraints

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration (spec §12).
- Every npm-ecosystem tool invocation is `npx --package=<exact> -- <bin>`, never a bare `npx <bin>` (dependency-confusion precedent, `docs/toolchain.md`) — this applies to `EslintLintRunner`, `TypeScriptRunner`, and `EslintComplexityRunner` alike, all of which run an audit-system-controlled, ephemeral copy of the tool against the target's own config files (`package.json`'s `scripts.lint`, `tsconfig.json`) rather than the target's own installed binary. PHP tools that ARE the target repo's own pinned devDependency (Pint via `vendor/bin/pint`) are invoked by their resolved local path instead, per `docs/toolchain.md`'s native-vs-ephemeral distinction (§4/Task 3) — that is not an npx call and carries no confusion risk.
- Linter/type-checker exit codes are NOT a pass/fail signal for usability: for Ruff, ESLint, mypy, tsc, PHPStan, Pint, and PHPMD, `exit_code == 0` means "ran clean, zero findings" and `exit_code == 1` (or `2` for PHPMD) means "ran successfully AND found violations" — both are usable results. Only exit codes signaling a tool/config crash (anything outside the tool's own documented pass/fail codes) mark a result unusable. Every normalizer in this plan filters on the tool's own documented usable-exit-code set, never on `exit_code == 0` alone (unlike 1.1/1.3's normalizers, which filter `exit_code == 0` because their tools use 0 for "ran, and here is the data" regardless of findings).
- PHP tool split: Pint = criterion 2.1 (lint), PHPStan = criterion 2.2 (type-check). Larastan's target-`composer.json`-mutation-and-revert workaround (`docs/toolchain.md`) applies only when the target is a Laravel project (detected via `laravel/framework` in `composer.json`'s `require`); non-Laravel PHP targets run bare PHPStan.
- Code duplication bands (jscpd, criterion 2.5): ≤3%→10, 3-5%→6, 5-10%→4, >10%→2.
- Cyclomatic complexity bands (criterion 2.3), applied to the single worst function/method per sub-project: ≤10→10, 11-20→6, 21-30→4, >30→2. All three language runners (radon, ESLint `complexity`, PHPMD `codesize`) must extract the actual numeric complexity per function, not just pass/fail against one threshold.
- Archetype B (2.1, 2.2) aggregation: summed-ratio across all relevant `ToolResult`s — `covered`/`applicable` counters summed before computing `score = (covered / applicable) * 10` (matches `module_size.py`'s pattern).
- Archetype A (2.3) aggregation: worst-band across sub-projects (matches `dependency_circularity.py`'s `worst_value` pattern). Criterion 2.5 (`jscpd`) is repo-scope, so it never has more than one relevant `ToolResult` — no cross-subproject aggregation needed.
- Repo-scope criteria (2.4, 2.5) never produce more than one `ToolResult` per audit — same convention as 1.2's `DesignDocRunner`.
- Missing-data / N/A is represented by not creating a `Score` row for that criterion in that `ScoringRun` (return `None`), consistent with every existing normalizer — `Score.na_reason` stays unused, matching current precedent.
- A real end-to-end audit run against an actual portfolio repo (not just this plan's synthetic fixtures) is required before the increment is considered done — Task 17.

---

### Task 1: `RuffRunner` (criterion 2.1, Python)

**Files:**
- Create: `src/radar_audit/runners/ruff_runner.py`
- Test: `tests/test_ruff_runner.py`

**Interfaces:**
- Consumes: `radar_audit.runner.RawToolOutput` (dataclass: `command: str`, `raw_output: dict[str, object]`, `exit_code: int`, `duration_ms: int`).
- Produces: `RuffRunner` (`tool_name="ruff-check"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"python"})`, `scope="subproject"`, `timeout_s=30`). `RawToolOutput.raw_output` shape: `{"violations": [<ruff JSON list entries>], "total_files": int}`. Each violation dict has `filename`, `code`, `message`, `location: {"row": int, "column": int}` (ruff's native `--output-format=json` shape). Consumed by Task 4 (`normalize_lint_pass_rate`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ruff_runner.py
from radar_audit.runners.ruff_runner import RuffRunner

from tests.git_helpers import init_git_repo


def test_reports_no_violations_on_clean_python(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a, b):\n    return a + b\n"})

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["violations"] == []
    assert result.raw_output["total_files"] == 1


def test_reports_violations_on_unused_import(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "import os\n\ndef add(a, b):\n    return a + b\n"})

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 1
    violations = result.raw_output["violations"]
    assert len(violations) == 1
    assert violations[0]["code"] == "F401"
    assert violations[0]["filename"].endswith("a.py")
    assert result.raw_output["total_files"] == 1


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": "def add(a, b):\n    return a + b\n",
            "src/vendor/b.py": "import os\n",
        },
    )

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "vendor"])

    assert result.raw_output["violations"] == []
    assert result.raw_output["total_files"] == 1


def test_reports_tool_identity():
    runner = RuffRunner()

    assert runner.tool_name == "ruff-check"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_ruff_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.ruff_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/ruff_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class RuffRunner:
    """Runs Ruff's linter (criterion 2.1, Python)."""

    tool_name = "ruff-check"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["uvx", "ruff", "check", "--output-format=json", str(target_path)]
        if exclude_paths:
            command.extend(["--exclude", ",".join(f"{p}/**" for p in exclude_paths)])

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            violations = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        total_files = self._count_python_files(target_path, exclude_paths)
        return RawToolOutput(
            command=" ".join(command),
            raw_output={"violations": violations, "total_files": total_files},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _count_python_files(self, target_path: Path, exclude_paths: list[Path]) -> int:
        count = 0
        for file_path in target_path.rglob("*.py"):
            if not file_path.is_file():
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            count += 1
        return count

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(excluded == file_path or excluded in file_path.parents for excluded in exclude_paths)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_ruff_runner.py -v`
Expected: PASS (4 tests). First run in a fresh environment needs network access to fetch `ruff` into the `uvx` cache.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/ruff_runner.py tests/test_ruff_runner.py
git commit -m "feat(radar-audit): add RuffRunner for criterion 2.1"
```

---

### Task 2: `EslintLintRunner` (criterion 2.1, JavaScript)

**Files:**
- Create: `src/radar_audit/runners/eslint_lint_runner.py`
- Test: `tests/test_eslint_lint_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `EslintLintRunner` (`tool_name="eslint"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"javascript"})`, `scope="subproject"`, `timeout_s=60`). Invocation per spec §4: `npx --package=eslint -- eslint <lint-script-scope> --format json`, run with `cwd=target_path` so the target's own config/plugins resolve normally (ephemeral ESLint binary, target-owned config — never a bare `.` scan, which would pick up unrelated generated artifacts per `docs/toolchain.md`'s ESLint scope caveat). `<lint-script-scope>` is derived from the sub-project's own `package.json`'s `scripts.lint` value: split on whitespace, drop tokens starting with `-` and the literal token `eslint`, resolve each remaining token relative to `target_path`, keep only tokens that resolve to an existing path, and fall back to `target_path` itself if none remain (e.g. no `package.json`, no `scripts.lint`, or no token resolves). `raw_output` shape: `{"results": [<ESLint JSON per-file entries>]}` (ESLint's native `--format=json`: list of `{"filePath": str, "messages": [{"ruleId": str|None, "message": str, "line": int, "column": int, "severity": int}], "errorCount": int, "warningCount": int}`). Consumed by Task 4.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_eslint_lint_runner.py
import json

import pytest

from radar_audit.runners.eslint_lint_runner import EslintLintRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, lint_script):
    (repo_path / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "1.0.0", "scripts": {"lint": lint_script}})
    )
    (repo_path / "eslint.config.js").write_text(
        "module.exports = [{ rules: { \"no-unused-vars\": \"error\" } }];\n"
    )


@pytest.mark.slow
def test_reports_no_violations_on_clean_js(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"})
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert all(entry["errorCount"] == 0 for entry in result.raw_output["results"])


@pytest.mark.slow
def test_reports_violations_on_unused_variable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"src/a.js": "export function add(a, b) {\n  const unused = 1;\n  return a + b;\n}\n"},
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    flagged = [e for e in result.raw_output["results"] if e["errorCount"] > 0]
    assert len(flagged) == 1


@pytest.mark.slow
def test_falls_back_to_target_path_when_no_lint_script(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"})
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))
    (repo_path / "eslint.config.js").write_text("module.exports = [{}];\n")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["results"]


def test_reports_tool_identity():
    runner = EslintLintRunner()

    assert runner.tool_name == "eslint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_eslint_lint_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.eslint_lint_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/eslint_lint_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class EslintLintRunner:
    """Runs the target's own lint script through an ephemeral ESLint (criterion 2.1)."""

    tool_name = "eslint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        scope_tokens = self._resolve_lint_scope(target_path)
        command = ["npx", "--package=eslint", "--", "eslint", *scope_tokens, "--format", "json"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"results": results},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _resolve_lint_scope(self, target_path: Path) -> list[str]:
        package_json = target_path / "package.json"
        if not package_json.exists():
            return ["."]

        data = json.loads(package_json.read_text())
        lint_script = data.get("scripts", {}).get("lint", "")
        tokens = [
            token for token in lint_script.split()
            if not token.startswith("-") and token != "eslint"
        ]
        resolved = [token for token in tokens if (target_path / token).exists()]
        return resolved if resolved else ["."]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_eslint_lint_runner.py -v -m ""`
Expected: PASS (4 tests). The three `@pytest.mark.slow` tests perform a real `npx` fetch and need network access; if `pytest.ini`/`pyproject.toml` doesn't already register a `slow` marker, add `markers = ["slow: real npx/npm fetch, needs network"]` under `[tool.pytest.ini_options]` in `radar-audit/pyproject.toml`.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/eslint_lint_runner.py tests/test_eslint_lint_runner.py pyproject.toml
git commit -m "feat(radar-audit): add EslintLintRunner for criterion 2.1"
```

---

### Task 3: `PintRunner` (criterion 2.1, PHP)

**Files:**
- Create: `src/radar_audit/runners/pint_runner.py`
- Test: `tests/test_pint_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `PintRunner` (`tool_name="pint"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"php"})`, `scope="subproject"`, `timeout_s=60`). Invokes the target's own `vendor/bin/pint --test --format=json` (native, matches the project's existing "native, repo-installed toolchain" pattern). `raw_output` shape: `{"result": "pass"}` when clean (confirmed shape from `docs/toolchain.md`'s smoke test), or `{"result": "fail", "files": [<per-file entries with at least a "file" key>]}` when violations exist — the fail-case shape is Pint's own JSON and must be confirmed against real output in Step 2 below; if it differs, adjust the parsing in `_extract_files` before moving to Step 4. Consumed by Task 4.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pint_runner.py
import subprocess

import pytest

from radar_audit.runners.pint_runner import PintRunner

from tests.git_helpers import init_git_repo


def _install_local_pint(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"laravel/pint": "^1.0"}}\n'
    )
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path, capture_output=True, text=True, timeout=120, check=True,
    )


@pytest.mark.slow
def test_reports_pass_on_correctly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A\n{\n}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["result"] == "pass"


@pytest.mark.slow
def test_reports_fail_on_badly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\nclass A{\npublic function f(){}\n}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["result"] == "fail"


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n"})

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PintRunner()

    assert runner.tool_name == "pint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pint_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pint_runner'`. When you write Step 3's implementation, run `vendor/bin/pint --test --format=json` by hand against the `test_reports_fail_on_badly_formatted_php` fixture first and inspect the real JSON — confirm or correct the `_extract_files` parsing below against that real output before relying on it.

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/pint_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PintRunner:
    """Runs the target's own locally-installed Laravel Pint (criterion 2.1)."""

    tool_name = "pint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        local_bin = target_path / "vendor" / "bin" / "pint"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"pint (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        command = [str(local_bin), "--test", "--format=json"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_pint_runner.py -v -m ""`
Expected: PASS (4 tests). The two `@pytest.mark.slow` tests need network access for `composer install`.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/pint_runner.py tests/test_pint_runner.py
git commit -m "feat(radar-audit): add PintRunner for criterion 2.1"
```

---

### Task 4: `normalize_lint_pass_rate` (criterion 2.1 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/lint_pass_rate.py`
- Test: `tests/test_normalize_lint_pass_rate.py`

**Interfaces:**
- Consumes: `RawToolOutput` shapes from Tasks 1-3 (`ruff-check`, `eslint`, `pint`); `get_or_create_scoring_run`, `get_criterion` from `radar_audit.normalizers.shared`; `Score`, `ScoringRun` from `radar_core.models.scoring`; `Finding` from `radar_core.models.finding`; `Criterion` from `radar_core.models.methodology`; `ToolResult` from `radar_core.models.audit`.
- Produces: `normalize_lint_pass_rate(session, scoring_run, criterion, tool_results) -> Score | None`, same signature shape as `normalize_module_size`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_lint_pass_rate.py
from radar_audit.normalizers.lint_pass_rate import normalize_lint_pass_rate
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, Repository, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.scoring import Score
from sqlmodel import select


def _make_audit(db_session):
    repo = Repository(name="fixture", clone_url="https://example.com/fixture.git")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def _setup(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Code quality", "Linter clean pass rate")
    return audit, scoring_run, criterion


def test_scores_ten_when_ruff_is_fully_clean(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ruff-check",
        tool_version="1.0.0",
        subproject_path="backend",
        raw_output={"violations": [], "total_files": 3},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_lowers_score_and_adds_findings_for_ruff_violations(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ruff-check",
        tool_version="1.0.0",
        subproject_path="backend",
        raw_output={
            "violations": [
                {"filename": "a.py", "code": "F401", "message": "unused import",
                 "location": {"row": 1, "column": 1}},
            ],
            "total_files": 2,
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 5.0  # 1 covered / 2 applicable * 10
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "a.py"


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_lint_pass_rate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.lint_pass_rate'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/lint_pass_rate.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"ruff-check", "eslint", "pint"}
_USABLE_EXIT_CODES = {0, 1}


def normalize_lint_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results
        if r.tool_name in _RELEVANT_TOOLS and r.exit_code in _USABLE_EXIT_CODES
    ]
    if not relevant:
        return None

    covered = 0
    applicable = 0
    for tool_result in relevant:
        file_covered, file_applicable = _score_files(session, scoring_run, criterion, tool_result)
        covered += file_covered
        applicable += file_applicable

    if applicable == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(covered / applicable) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _score_files(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    if tool_result.tool_name == "ruff-check":
        return _score_ruff(session, scoring_run, criterion, tool_result)
    if tool_result.tool_name == "eslint":
        return _score_eslint(session, scoring_run, criterion, tool_result)
    return _score_pint(session, scoring_run, criterion, tool_result)


def _score_ruff(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    applicable = tool_result.raw_output.get("total_files", 0)
    violations = tool_result.raw_output.get("violations", [])
    flagged_files = {v["filename"] for v in violations}
    for violation in violations:
        _add_finding(
            session, scoring_run, criterion, tool_result,
            f"{violation['code']}: {violation['message']}",
            file=violation["filename"], line=violation["location"]["row"],
        )
    return applicable - len(flagged_files), applicable


def _score_eslint(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    results = tool_result.raw_output.get("results", [])
    applicable = len(results)
    covered = 0
    for entry in results:
        if entry["errorCount"] == 0:
            covered += 1
            continue
        for message in entry["messages"]:
            _add_finding(
                session, scoring_run, criterion, tool_result,
                f"{message.get('ruleId') or 'parse-error'}: {message['message']}",
                file=entry["filePath"], line=message.get("line"),
            )
    return covered, applicable


def _score_pint(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    if tool_result.raw_output.get("result") == "pass":
        return 1, 1  # single subproject-level pass/fail signal, no per-file breakdown available
    files = tool_result.raw_output.get("files", [])
    for entry in files:
        _add_finding(
            session, scoring_run, criterion, tool_result,
            "file does not conform to the project's Pint style", file=entry.get("file"),
        )
    return 0, 1


def _add_finding(session, scoring_run, criterion, tool_result, description, file=None, line=None):
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=description,
            file=file,
            line=line,
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_lint_pass_rate.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/normalizers/lint_pass_rate.py tests/test_normalize_lint_pass_rate.py
git commit -m "feat(radar-audit): add normalize_lint_pass_rate for criterion 2.1"
```

---

### Task 5: `MypyRunner` (criterion 2.2, Python)

**Files:**
- Create: `src/radar_audit/runners/mypy_runner.py`
- Test: `tests/test_mypy_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `MypyRunner` (`tool_name="mypy"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"python"})`, `scope="subproject"`, `timeout_s=60`). `raw_output` shape: `{"diagnostics": [<one dict per mypy JSON-line diagnostic: "file","line","column","message","code","severity">], "total_files": int}`. If the target declares a mypy plugin (`[tool.mypy].plugins` in `pyproject.toml`, or a `plugins =` line in `mypy.ini`), mypy is run via an ephemeral `uvx --with-requirements requirements.txt --with mypy mypy` install of the target's own runtime deps so the plugin can resolve real types; otherwise a bare `uvx mypy` is used. Consumed by Task 8.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mypy_runner.py
from radar_audit.runners.mypy_runner import MypyRunner

from tests.git_helpers import init_git_repo


def test_reports_no_diagnostics_on_well_typed_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a: int, b: int) -> int:\n    return a + b\n"})

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["diagnostics"] == []


def test_reports_a_type_error(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"src/a.py": "def add(a: int, b: int) -> int:\n    return a + b\n\nadd('x', 1)\n"},
    )

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 1
    diagnostics = result.raw_output["diagnostics"]
    assert any(d["severity"] == "error" for d in diagnostics)


def test_reports_tool_identity():
    runner = MypyRunner()

    assert runner.tool_name == "mypy"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_mypy_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.mypy_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/mypy_runner.py
from __future__ import annotations

import json
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class MypyRunner:
    """Runs mypy (criterion 2.2, Python), branching on plugin detection per toolchain.md."""

    tool_name = "mypy"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        if self._has_plugin(target_path):
            command = ["uvx", "--with", "mypy"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            command.extend(["mypy", "--output=json", "--ignore-missing-imports", str(target_path)])
        else:
            command = ["uvx", "mypy", "--output=json", "--ignore-missing-imports", str(target_path)]

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        diagnostics = []
        for line in completed.stdout.splitlines():
            try:
                diagnostics.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        total_files = self._count_python_files(target_path, exclude_paths)
        return RawToolOutput(
            command=" ".join(command),
            raw_output={"diagnostics": diagnostics, "total_files": total_files},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _has_plugin(self, target_path: Path) -> bool:
        pyproject = target_path / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            if data.get("tool", {}).get("mypy", {}).get("plugins"):
                return True
        mypy_ini = target_path / "mypy.ini"
        if mypy_ini.exists() and "plugins" in mypy_ini.read_text():
            return True
        return False

    def _count_python_files(self, target_path: Path, exclude_paths: list[Path]) -> int:
        count = 0
        for file_path in target_path.rglob("*.py"):
            if not file_path.is_file():
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            count += 1
        return count

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(excluded == file_path or excluded in file_path.parents for excluded in exclude_paths)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_mypy_runner.py -v`
Expected: PASS (3 tests). First run in a fresh environment needs network access to fetch `mypy` into the `uvx` cache.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/mypy_runner.py tests/test_mypy_runner.py
git commit -m "feat(radar-audit): add MypyRunner for criterion 2.2"
```

---

### Task 6: `TypeScriptRunner` (criterion 2.2, JavaScript)

**Files:**
- Create: `src/radar_audit/runners/typescript_runner.py`
- Test: `tests/test_typescript_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `TypeScriptRunner` (`tool_name="tsc"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"javascript"})`, `scope="subproject"`, `timeout_s=60`). Invocation per spec §5: if the sub-project's `package.json` lists `vue-tsc` as a devDependency, `npx --package=vue-tsc -- vue-tsc --noEmit`; otherwise `npx --package=typescript -- tsc --noEmit` (ephemeral, package explicitly pinned per the Global Constraints' npx rule; run with `cwd=target_path` so the target's own `tsconfig.json` is picked up). `raw_output` shape: `{"diagnostics": [{"file": str, "line": int, "column": int, "code": str, "message": str}], "total_files": int}`, parsed from the plain-text `file(line,col): error TSxxxx: message` output (neither `tsc` nor `vue-tsc` has a native JSON reporter). Consumed by Task 8.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_typescript_runner.py
import json

import pytest

from radar_audit.runners.typescript_runner import TypeScriptRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, devDependencies=None):
    (repo_path / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "1.0.0", "devDependencies": devDependencies or {}})
    )
    (repo_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True, "noEmit": True}})
    )


@pytest.mark.slow
def test_reports_no_diagnostics_on_well_typed_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\n"})
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["diagnostics"] == []


@pytest.mark.slow
def test_reports_a_type_error(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"src/a.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\nadd('x', 1);\n"},
    )
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert len(result.raw_output["diagnostics"]) >= 1


def test_uses_typescript_package_when_vue_tsc_not_a_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary({"devDependencies": {}}) == ("typescript", "tsc")


def test_uses_vue_tsc_package_when_declared_as_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary(
        {"devDependencies": {"vue-tsc": "^2.0.0"}}
    ) == ("vue-tsc", "vue-tsc")


def test_reports_tool_identity():
    runner = TypeScriptRunner()

    assert runner.tool_name == "tsc"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_typescript_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.typescript_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/typescript_runner.py
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\): error (?P<code>TS\d+): (?P<message>.+)$"
)
_SOURCE_EXTENSIONS = {".ts", ".tsx", ".vue"}
_SKIP_DIRNAMES = {"node_modules", "dist", "build"}


class TypeScriptRunner:
    """Runs an ephemeral tsc/vue-tsc against the target's own tsconfig.json (criterion 2.2)."""

    tool_name = "tsc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        package_json = target_path / "package.json"
        data = json.loads(package_json.read_text()) if package_json.exists() else {}
        package_name, binary_name = self._resolve_package_and_binary(data)

        command = ["npx", f"--package={package_name}", "--", binary_name, "--noEmit"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        diagnostics = []
        for line in completed.stdout.splitlines():
            match = _DIAGNOSTIC_PATTERN.match(line.strip())
            if match:
                diagnostics.append({
                    "file": match.group("file"),
                    "line": int(match.group("line")),
                    "column": int(match.group("column")),
                    "code": match.group("code"),
                    "message": match.group("message"),
                })

        total_files = self._count_source_files(target_path, exclude_paths)
        return RawToolOutput(
            command=" ".join(command),
            raw_output={"diagnostics": diagnostics, "total_files": total_files},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _resolve_package_and_binary(self, package_json_data: dict[str, object]) -> tuple[str, str]:
        dev_dependencies = package_json_data.get("devDependencies", {})
        if "vue-tsc" in dev_dependencies:
            return "vue-tsc", "vue-tsc"
        return "typescript", "tsc"

    def _count_source_files(self, target_path: Path, exclude_paths: list[Path]) -> int:
        count = 0
        for file_path in target_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            count += 1
        return count

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(excluded == file_path or excluded in file_path.parents for excluded in exclude_paths)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_typescript_runner.py -v -m ""`
Expected: PASS (5 tests). The two `@pytest.mark.slow` tests need network access for the `npx` fetch.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/typescript_runner.py tests/test_typescript_runner.py
git commit -m "feat(radar-audit): add TypeScriptRunner for criterion 2.2"
```

---

### Task 7: `PhpstanRunner` (criterion 2.2, PHP)

**Files:**
- Create: `src/radar_audit/runners/phpstan_runner.py`
- Test: `tests/test_phpstan_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `PhpstanRunner` (`tool_name="phpstan"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"php"})`, `scope="subproject"`, `timeout_s=120`). `raw_output` shape: PHPStan's native `--error-format=json`: `{"totals": {"errors": int, "file_errors": int}, "files": {"<path>": {"errors": int, "messages": [{"message": str, "line": int}]}}, "errors": []}`. Mutates the target's own `composer.json`/`composer.lock` to `require --dev phpstan/phpstan`, runs the analysis, then reverts both files to their original bytes and re-runs `composer install` — this exact byte-identical-revert behavior must be tested. Consumed by Task 8.

**Ruling — refines spec §5's literal wording:** spec §5 reads "`composer require --dev phpstan/phpstan larastan/larastan`" unconditionally. `docs/toolchain.md`'s own Larastan section documents that Larastan's `extension.neon` resolves the target's Laravel version at config-parse time and fails before any file is even selected — a target with no `laravel/framework` dependency has no such version to resolve. Installing `larastan/larastan` unconditionally would therefore crash `PhpstanRunner` outright on any non-Laravel PHP target. This task installs `larastan/larastan` only when the target's own `composer.json` declares `laravel/framework` in its `require` section, keeping spec §5's documented Laravel behavior intact while avoiding a guaranteed crash on plain PHP targets. Cost if wrong: a non-Laravel-but-Laravel-like target that needs Larastan's stubs without declaring `laravel/framework` directly would fall back to plain PHPStan and show elevated false positives — acceptable, since no in-scope repo matches that shape today (Global Constraints, §12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_phpstan_runner.py
import subprocess

import pytest

from radar_audit.runners.phpstan_runner import PhpstanRunner

from tests.git_helpers import init_git_repo


def _init_composer_project(repo_path):
    (repo_path / "composer.json").write_text('{"name": "fixture/fixture"}\n')
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path, capture_output=True, text=True, timeout=120, check=True,
    )


@pytest.mark.slow
def test_reports_no_errors_on_well_typed_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A\n{\n    public function add(int $a, int $b): int\n    {\n        return $a + $b;\n    }\n}\n"})
    _init_composer_project(repo_path)

    runner = PhpstanRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["totals"]["errors"] == 0


@pytest.mark.slow
def test_reverts_composer_json_and_lock_byte_identical(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A\n{\n}\n"})
    _init_composer_project(repo_path)
    original_json = (repo_path / "composer.json").read_bytes()
    original_lock = (repo_path / "composer.lock").read_bytes()

    runner = PhpstanRunner()
    runner.run(repo_path, exclude_paths=[])

    assert (repo_path / "composer.json").read_bytes() == original_json
    assert (repo_path / "composer.lock").read_bytes() == original_lock


def test_reports_tool_identity():
    runner = PhpstanRunner()

    assert runner.tool_name == "phpstan"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_phpstan_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.phpstan_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/phpstan_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_LARASTAN_EXTENSION_NEON = (
    "includes:\n    - vendor/larastan/larastan/extension.neon\nparameters:\n    level: 5\n"
)
_BARE_NEON = "parameters:\n    level: 5\n"


class PhpstanRunner:
    """Runs PHPStan (criterion 2.2, PHP) via a mutate-target/revert workaround for Larastan."""

    tool_name = "phpstan"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        composer_json = target_path / "composer.json"
        composer_lock = target_path / "composer.lock"
        original_json = composer_json.read_bytes() if composer_json.exists() else None
        original_lock = composer_lock.read_bytes() if composer_lock.exists() else None

        is_laravel = self._is_laravel(composer_json)
        dev_packages = ["phpstan/phpstan"]
        if is_laravel:
            dev_packages.append("larastan/larastan")

        start = time.monotonic()
        try:
            subprocess.run(
                ["composer", "require", "--dev", *dev_packages, "--no-interaction"],
                cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
            extension_neon = target_path / "_radar_audit_phpstan.neon"
            extension_neon.write_text(_LARASTAN_EXTENSION_NEON if is_laravel else _BARE_NEON)
            try:
                command = [
                    "vendor/bin/phpstan", "analyse", "--configuration", str(extension_neon),
                    "--error-format=json", "--no-progress", str(target_path),
                ]
                completed = subprocess.run(
                    command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
                )
            finally:
                extension_neon.unlink(missing_ok=True)
        finally:
            if original_json is not None:
                composer_json.write_bytes(original_json)
            else:
                composer_json.unlink(missing_ok=True)
            if original_lock is not None:
                composer_lock.write_bytes(original_lock)
            else:
                composer_lock.unlink(missing_ok=True)
            subprocess.run(
                ["composer", "install", "--no-interaction"],
                cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _is_laravel(self, composer_json: Path) -> bool:
        if not composer_json.exists():
            return False
        data = json.loads(composer_json.read_text())
        return "laravel/framework" in data.get("require", {})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_phpstan_runner.py -v -m ""`
Expected: PASS (3 tests). The two `@pytest.mark.slow` tests need network access for `composer require`/`composer install`.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/phpstan_runner.py tests/test_phpstan_runner.py
git commit -m "feat(radar-audit): add PhpstanRunner for criterion 2.2"
```

---

### Task 8: `normalize_type_check_pass_rate` (criterion 2.2 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/type_check_pass_rate.py`
- Test: `tests/test_normalize_type_check_pass_rate.py`

**Interfaces:**
- Consumes: `RawToolOutput` shapes from Tasks 5-7 (`mypy`, `tsc`, `phpstan`).
- Produces: `normalize_type_check_pass_rate(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_type_check_pass_rate.py
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.type_check_pass_rate import normalize_type_check_pass_rate
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, Repository, ToolResult
from radar_core.models.finding import Finding
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", clone_url="https://example.com/fixture.git")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Code quality", "Type-checking pass")
    return audit, scoring_run, criterion


def test_scores_ten_when_mypy_is_fully_clean(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="mypy", tool_version="1.0.0", subproject_path="backend",
        raw_output={"diagnostics": [], "total_files": 3}, exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_lowers_score_and_adds_findings_for_phpstan_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="phpstan", tool_version="1.0.0", subproject_path="backend",
        raw_output={
            "totals": {"errors": 1, "file_errors": 1},
            "files": {"src/A.php": {"errors": 1, "messages": [{"message": "bad type", "line": 5}]}},
            "errors": [],
        },
        exit_code=1, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "src/A.php"


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_type_check_pass_rate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.type_check_pass_rate'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/type_check_pass_rate.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"mypy", "tsc", "phpstan"}
_USABLE_EXIT_CODES = {0, 1}
_SOURCE_EXTENSIONS_BY_TOOL = {"mypy": "total_files", "tsc": "total_files"}


def normalize_type_check_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results
        if r.tool_name in _RELEVANT_TOOLS and r.exit_code in _USABLE_EXIT_CODES
    ]
    if not relevant:
        return None

    covered = 0
    applicable = 0
    for tool_result in relevant:
        file_covered, file_applicable = _score_files(session, scoring_run, criterion, tool_result)
        covered += file_covered
        applicable += file_applicable

    if applicable == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(covered / applicable) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _score_files(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    if tool_result.tool_name == "phpstan":
        return _score_phpstan(session, scoring_run, criterion, tool_result)
    return _score_diagnostics_tool(session, scoring_run, criterion, tool_result)


def _score_diagnostics_tool(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    applicable = tool_result.raw_output.get("total_files", 0)
    diagnostics = tool_result.raw_output.get("diagnostics", [])
    flagged_files = {d["file"] for d in diagnostics}
    for diagnostic in diagnostics:
        _add_finding(
            session, scoring_run, criterion, tool_result,
            f"{diagnostic.get('code', 'type-error')}: {diagnostic['message']}",
            file=diagnostic["file"], line=diagnostic.get("line"),
        )
    return applicable - len(flagged_files), applicable


def _score_phpstan(session, scoring_run, criterion, tool_result) -> tuple[int, int]:
    files_with_errors = tool_result.raw_output.get("files", {})
    total_errors = tool_result.raw_output.get("totals", {}).get("file_errors", 0)
    for file_path, entry in files_with_errors.items():
        for message in entry.get("messages", []):
            _add_finding(
                session, scoring_run, criterion, tool_result,
                message["message"], file=file_path, line=message.get("line"),
            )
    # PHPStan's JSON only lists files WITH errors; the clean-file count isn't
    # directly available, so treat "no errors" as the applicable=covered=1 signal
    # and each errored file as one uncovered unit against the same denominator.
    if total_errors == 0:
        return 1, 1
    return 0, len(files_with_errors) or 1


def _add_finding(session, scoring_run, criterion, tool_result, description, file=None, line=None):
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.MEDIUM,
            description=description,
            file=file,
            line=line,
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_type_check_pass_rate.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/normalizers/type_check_pass_rate.py tests/test_normalize_type_check_pass_rate.py
git commit -m "feat(radar-audit): add normalize_type_check_pass_rate for criterion 2.2"
```

---

### Task 9: `RadonComplexityRunner` (criterion 2.3, Python)

**Files:**
- Create: `src/radar_audit/runners/radon_complexity_runner.py`
- Test: `tests/test_radon_complexity_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `RadonComplexityRunner` (`tool_name="radon-cc"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"python"})`, `scope="subproject"`, `timeout_s=30`). `raw_output` shape: radon's native `cc --json`: `{"<file>": [{"type": str, "name": str, "complexity": int, "rank": str}]}`. Consumed by Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_radon_complexity_runner.py
from radar_audit.runners.radon_complexity_runner import RadonComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_FUNCTION = "def add(a, b):\n    return a + b\n"

_COMPLEX_FUNCTION = "def classify(n):\n" + "".join(
    f"    if n == {i}:\n        return {i}\n" for i in range(15)
) + "    return -1\n"


def test_reports_low_complexity_on_a_simple_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _SIMPLE_FUNCTION})

    runner = RadonComplexityRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    blocks = next(iter(result.raw_output.values()))
    assert blocks[0]["complexity"] <= 2


def test_reports_high_complexity_on_a_branchy_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _COMPLEX_FUNCTION})

    runner = RadonComplexityRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    blocks = next(iter(result.raw_output.values()))
    assert blocks[0]["complexity"] >= 11


def test_reports_tool_identity():
    runner = RadonComplexityRunner()

    assert runner.tool_name == "radon-cc"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_radon_complexity_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.radon_complexity_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/radon_complexity_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_GLOB_SUFFIXES = (
    "/.venv/*", "/__pycache__/*", "/node_modules/*", "/vendor/*", "/dist/*", "/build/*",
)


class RadonComplexityRunner:
    """Runs radon's cyclomatic complexity analysis (criterion 2.3, Python)."""

    tool_name = "radon-cc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        patterns = [f"{target_path}{suffix}" for suffix in _SKIP_GLOB_SUFFIXES]
        patterns.extend(f"{excluded}/*" for excluded in exclude_paths)
        command = ["uvx", "radon", "cc", "--json", "-e", ",".join(patterns), str(target_path)]

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_radon_complexity_runner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/radon_complexity_runner.py tests/test_radon_complexity_runner.py
git commit -m "feat(radar-audit): add RadonComplexityRunner for criterion 2.3"
```

---

### Task 10: `EslintComplexityRunner` (criterion 2.3, JavaScript)

**Files:**
- Create: `src/radar_audit/runners/eslint_complexity_runner.py`
- Test: `tests/test_eslint_complexity_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `EslintComplexityRunner` (`tool_name="eslint-complexity"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"javascript"})`, `scope="subproject"`, `timeout_s=60`). Invocation per spec §6: `npx --package=eslint -- eslint -c <audit-owned temp config> <target_path> --format json` (ephemeral, package pinned per the Global Constraints' npx rule; run with `cwd=target_path`), using a minimal audit-authored flat config enabling only the `complexity` rule at `["error", 1]` so every function is flagged with its real complexity number in the message (`"...has a complexity of 14. Maximum allowed is 1."`), independent of the repo's own lint config. `raw_output` shape: `{"complexities": [{"file": str, "line": int, "complexity": int}]}`, parsed by extracting the numeric value from each violation message. Consumed by Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_eslint_complexity_runner.py
import json

import pytest

from radar_audit.runners.eslint_complexity_runner import EslintComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_FUNCTION = "export function add(a, b) {\n  return a + b;\n}\n"

_COMPLEX_FUNCTION = "export function classify(n) {\n" + "".join(
    f"  if (n === {i}) return {i};\n" for i in range(15)
) + "  return -1;\n}\n"


def _write_package_json(repo_path):
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))


@pytest.mark.slow
def test_reports_low_complexity_on_a_simple_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _SIMPLE_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) <= 2


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _COMPLEX_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) >= 11


def test_reports_tool_identity():
    runner = EslintComplexityRunner()

    assert runner.tool_name == "eslint-complexity"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_eslint_complexity_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.eslint_complexity_runner'`. When writing Step 3, run the audit-owned config by hand against `_COMPLEX_FUNCTION` first and confirm the installed ESLint major version's flat-config `-c` handling matches what's coded below — ESLint 9's flat-config mode resolves `-c` differently from ESLint 8's `.eslintrc`-based mode; adjust before Step 4 if it differs.

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/eslint_complexity_runner.py
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_AUDIT_CONFIG = 'module.exports = [{ rules: { complexity: ["error", 1] } }];\n'
_COMPLEXITY_PATTERN = re.compile(r"complexity of (\d+)")


class EslintComplexityRunner:
    """Runs an ephemeral ESLint with an audit-owned max:1 complexity config (criterion 2.3)."""

    tool_name = "eslint-complexity"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".config.js", delete=False, dir=target_path
        ) as config_file:
            config_file.write(_AUDIT_CONFIG)
            config_path = Path(config_file.name)

        try:
            command = [
                "npx", "--package=eslint", "--", "eslint",
                "-c", str(config_path), str(target_path), "--format", "json",
            ]
            for excluded in exclude_paths:
                command.extend(["--ignore-pattern", str(excluded)])

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
                    complexities.append({
                        "file": entry["filePath"],
                        "line": message.get("line"),
                        "complexity": int(match.group(1)),
                    })

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"complexities": complexities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_eslint_complexity_runner.py -v -m ""`
Expected: PASS (3 tests). The two `@pytest.mark.slow` tests need network access for the `npx` fetch.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/eslint_complexity_runner.py tests/test_eslint_complexity_runner.py
git commit -m "feat(radar-audit): add EslintComplexityRunner for criterion 2.3"
```

---

### Task 11: `PhpmdComplexityRunner` (criterion 2.3, PHP)

**Files:**
- Create: `src/radar_audit/runners/phpmd_complexity_runner.py`
- Test: `tests/test_phpmd_complexity_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `PhpmdComplexityRunner` (`tool_name="phpmd-codesize"`, `tool_version="1.0.0"`, `supported_stacks=frozenset({"php"})`, `scope="subproject"`, `timeout_s=60`). Runs PHPMD's `codesize` ruleset from an isolated, per-invocation scratch Composer project (own `vendor/`, never shared with the target's own dependencies), against the target directory. `raw_output` shape: `{"violations": [{"file": str, "line": int, "complexity": int}]}`, parsed from PHPMD's XML output (`<file name="..."><violation beginline="N" ...>message text</violation></file>`) by extracting the numeric value from each `"Cyclomatic Complexity of N"` message. Consumed by Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_phpmd_complexity_runner.py
import pytest

from radar_audit.runners.phpmd_complexity_runner import PhpmdComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_METHOD = "<?php\n\nclass A\n{\n    public function add(int $a, int $b): int\n    {\n        return $a + $b;\n    }\n}\n"

_COMPLEX_METHOD_BODY = "".join(f"        if ($n === {i}) return {i};\n" for i in range(15))
_COMPLEX_METHOD = (
    "<?php\n\nclass A\n{\n    public function classify(int $n): int\n    {\n"
    + _COMPLEX_METHOD_BODY
    + "        return -1;\n    }\n}\n"
)


@pytest.mark.slow
def test_reports_no_violations_on_a_simple_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _SIMPLE_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["violations"] == []


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _COMPLEX_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    violations = result.raw_output["violations"]
    assert violations and max(v["complexity"] for v in violations) >= 11


def test_reports_tool_identity():
    runner = PhpmdComplexityRunner()

    assert runner.tool_name == "phpmd-codesize"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_phpmd_complexity_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.phpmd_complexity_runner'`. When writing Step 3, run the scratch-project PHPMD invocation by hand against `_COMPLEX_METHOD` first and confirm PHPMD's exit code (0/1/2 convention) and the exact `Cyclomatic Complexity of N` wording — adjust `_USABLE_EXIT_CODES`-equivalent handling and the regex in Task 12's normalizer if they differ.

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/phpmd_complexity_runner.py
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
                cwd=scratch, capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
            subprocess.run(
                ["composer", "require", "--dev", "phpmd/phpmd", "--no-interaction"],
                cwd=scratch, capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
            command = [str(scratch / "vendor" / "bin" / "phpmd"), str(target_path), "xml", "codesize"]
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
                    violations.append({
                        "file": file_name,
                        "line": int(violation.get("beginline", 0)),
                        "complexity": int(match.group(1)),
                    })

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"violations": violations},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_phpmd_complexity_runner.py -v -m ""`
Expected: PASS (3 tests). The two `@pytest.mark.slow` tests need network access for `composer require`.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/phpmd_complexity_runner.py tests/test_phpmd_complexity_runner.py
git commit -m "feat(radar-audit): add PhpmdComplexityRunner for criterion 2.3"
```

---

### Task 12: `normalize_cyclomatic_complexity` (criterion 2.3 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/cyclomatic_complexity.py`
- Test: `tests/test_normalize_cyclomatic_complexity.py`

**Interfaces:**
- Consumes: `RawToolOutput` shapes from Tasks 9-11 (`radon-cc`, `eslint-complexity`, `phpmd-codesize`).
- Produces: `normalize_cyclomatic_complexity(session, scoring_run, criterion, tool_results) -> Score | None`. Worst-band aggregation across sub-projects (matches `dependency_circularity.py`'s pattern): each relevant `ToolResult` contributes its own worst function's band value, and the minimum across all results is the final score.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_cyclomatic_complexity.py
from radar_audit.normalizers.cyclomatic_complexity import normalize_cyclomatic_complexity
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence
from radar_core.models.audit import Audit, Repository, ToolResult
from radar_core.models.finding import Finding
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", clone_url="https://example.com/fixture.git")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Code quality", "Cyclomatic complexity")
    return audit, scoring_run, criterion


def test_scores_ten_when_radon_worst_complexity_is_low(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="radon-cc", tool_version="1.0.0", subproject_path="backend",
        raw_output={"src/a.py": [{"type": "function", "name": "add", "complexity": 3, "rank": "A"}]},
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_finding_and_score_confidence_is_high_for_radon(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="radon-cc", tool_version="1.0.0", subproject_path="backend",
        raw_output={
            "src/a.py": [{"type": "function", "name": "classify", "complexity": 35, "rank": "F"}]
        },
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert findings[0].confidence == Confidence.HIGH


def test_finding_and_score_confidence_is_medium_for_eslint_complexity(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="eslint-complexity", tool_version="1.0.0", subproject_path="frontend",
        raw_output={
            "src/a.js": [{"type": "function", "name": "classify", "complexity": 35, "rank": "F"}]
        },
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.MEDIUM
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert findings[0].confidence == Confidence.MEDIUM


def test_scores_low_and_adds_a_finding_when_worst_complexity_is_very_high(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="radon-cc", tool_version="1.0.0", subproject_path="backend",
        raw_output={
            "src/a.py": [{"type": "function", "name": "classify", "complexity": 35, "rank": "F"}]
        },
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_cyclomatic_complexity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.cyclomatic_complexity'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/cyclomatic_complexity.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"radon-cc", "eslint-complexity", "phpmd-codesize"}
# Bands: <=10->10, 11-20->6, 21-30->4, >30->2 (spec §3.3). Resolved during
# design but provisional -- not yet calibrated against real portfolio data
# (spec §11), same discipline as 2.1's 30-line/400-LOC thresholds.
_BANDS: tuple[tuple[int, float], ...] = ((10, 10.0), (20, 6.0), (30, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0
_WORST_COMPLEXITY_THRESHOLD_FOR_FINDING = 10


def normalize_cyclomatic_complexity(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name in _RELEVANT_TOOLS and r.exit_code == 0]
    if not relevant:
        return None

    worst_value: float | None = None
    worst_confidence: Confidence | None = None
    for tool_result in relevant:
        blocks = _extract_blocks(tool_result)
        if not blocks:
            continue
        tool_confidence = _confidence_for_tool(tool_result.tool_name)
        worst_block = max(blocks, key=lambda b: b["complexity"])
        if worst_block["complexity"] > _WORST_COMPLEXITY_THRESHOLD_FOR_FINDING:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.MEDIUM,
                    description=(
                        f"{worst_block.get('name', 'function')} has cyclomatic complexity "
                        f"{worst_block['complexity']}"
                    ),
                    file=worst_block.get("file"),
                    line=worst_block.get("line"),
                    confidence=tool_confidence,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
        value = _band_value(worst_block["complexity"])
        if worst_value is None or value < worst_value:
            worst_value = value
            worst_confidence = tool_confidence

    if worst_value is None or worst_confidence is None:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=worst_value,
        confidence=worst_confidence,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(complexity: int) -> float:
    for max_complexity, value in _BANDS:
        if complexity <= max_complexity:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _confidence_for_tool(tool_name: str) -> Confidence:
    # radon is validated (spec §9); the JS/PHP candidates stay MEDIUM until
    # smoke-tested against a real repo (Task 17).
    return Confidence.HIGH if tool_name == "radon-cc" else Confidence.MEDIUM


def _extract_blocks(tool_result: ToolResult) -> list[dict[str, object]]:
    if tool_result.tool_name == "radon-cc":
        blocks = []
        for file_path, entries in tool_result.raw_output.items():
            for entry in entries:
                blocks.append({
                    "complexity": entry["complexity"], "name": entry["name"],
                    "file": file_path, "line": entry.get("lineno"),
                })
        return blocks
    if tool_result.tool_name == "eslint-complexity":
        return [
            {"complexity": c["complexity"], "name": None, "file": c["file"], "line": c["line"]}
            for c in tool_result.raw_output.get("complexities", [])
        ]
    return [
        {"complexity": v["complexity"], "name": None, "file": v["file"], "line": v["line"]}
        for v in tool_result.raw_output.get("violations", [])
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_cyclomatic_complexity.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/normalizers/cyclomatic_complexity.py tests/test_normalize_cyclomatic_complexity.py
git commit -m "feat(radar-audit): add normalize_cyclomatic_complexity for criterion 2.3"
```

---

### Task 13: `PreCommitGateRunner` (criterion 2.4, repo-scope)

**Files:**
- Create: `src/radar_audit/runners/precommit_gate_runner.py`
- Test: `tests/test_precommit_gate_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `PreCommitGateRunner` (`tool_name="pre-commit-gate"`, `tool_version="1.0.0"`, `supported_stacks=frozenset()`, `scope="repo"`, `timeout_s=10`, no subprocess). `raw_output` shape: `{"tier": "pre-commit"|"husky"|"lefthook"|"none", "domains": [str, ...], "cells": {"<domain>:<validator_type>": bool}}` where `domains` are the repo's own detected domains (`"backend"`, `"frontend"`) via a lightweight local manifest scan, and `cells` marks every applicable `{lint, format, type-check} x domain` combination as covered or not, per the D12 coverage-matrix mechanics in `docs/system-design.md`§6. Consumed by Task 14.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_precommit_gate_runner.py
from radar_audit.runners.precommit_gate_runner import PreCommitGateRunner

from tests.git_helpers import init_git_repo


def test_detects_pre_commit_config_and_covers_matching_cells(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pyproject.toml": "[tool.ruff]\n",
            "src/a.py": "x = 1\n",
            ".pre-commit-config.yaml": (
                "repos:\n"
                "  - repo: local\n"
                "    hooks:\n"
                "      - id: ruff\n"
                "      - id: mypy\n"
            ),
        },
    )

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tier"] == "pre-commit"
    assert result.raw_output["cells"]["backend:lint"] is True
    assert result.raw_output["cells"]["backend:type-check"] is True


def test_detects_husky_lint_staged_chain(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": (
                '{"name": "fixture", "lint-staged": {"*.js": ["eslint --fix"]}}\n'
            ),
            "src/a.js": "const a = 1;\n",
            ".husky/pre-commit": "npx lint-staged\n",
        },
    )

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "husky"
    assert result.raw_output["cells"]["frontend:lint"] is True


def test_reports_none_when_no_gate_configuration_found(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[tool.ruff]\n", "src/a.py": "x = 1\n"})

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "none"
    assert result.raw_output["cells"] == {}


def test_reports_tool_identity():
    runner = PreCommitGateRunner()

    assert runner.tool_name == "pre-commit-gate"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_precommit_gate_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.precommit_gate_runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/precommit_gate_runner.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import yaml

from radar_audit.runner import RawToolOutput

# hook id -> (validator_type, domain). Domain-only hooks (format/lint on both
# domains at once, e.g. a repo-wide prettier hook) are not modeled: each hook
# id maps to exactly one domain, matching how these tools are typically wired
# per-language in a single pre-commit config.
_HOOK_LOOKUP: dict[str, tuple[str, str]] = {
    "ruff": ("lint", "backend"),
    "ruff-format": ("format", "backend"),
    "mypy": ("type-check", "backend"),
    "eslint": ("lint", "frontend"),
    "prettier": ("format", "frontend"),
    "vue-tsc": ("type-check", "frontend"),
    "tsc": ("type-check", "frontend"),
    "pint": ("lint", "backend"),
    "laravel-pint": ("lint", "backend"),
    "phpstan": ("type-check", "backend"),
}
_VALIDATOR_TYPES = ("lint", "format", "type-check")


class PreCommitGateRunner:
    """Detects pre-commit/husky/lefthook coverage over {lint,format,type-check} x domain (criterion 2.4)."""

    tool_name = "pre-commit-gate"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()
        domains = self._detect_domains(target_path)

        hook_ids = self._detect_pre_commit_hooks(target_path)
        tier = "pre-commit" if hook_ids else None
        if tier is None:
            hook_ids = self._detect_husky_hooks(target_path)
            tier = "husky" if hook_ids else None
        if tier is None:
            hook_ids = self._detect_lefthook_hooks(target_path)
            tier = "lefthook" if hook_ids else None
        if tier is None:
            tier = "none"
            hook_ids = set()

        cells: dict[str, bool] = {}
        for validator_type, domain in _HOOK_LOOKUP.values():
            if domain in domains:
                cells[f"{domain}:{validator_type}"] = False
        for hook_id in hook_ids:
            mapping = _HOOK_LOOKUP.get(hook_id)
            if mapping is None:
                continue
            validator_type, domain = mapping
            if domain in domains:
                cells[f"{domain}:{validator_type}"] = True

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"filesystem-check {target_path}",
            raw_output={"tier": tier, "domains": sorted(domains), "cells": cells},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _detect_domains(self, target_path: Path) -> set[str]:
        domains: set[str] = set()
        candidates = [target_path]
        if target_path.is_dir():
            candidates.extend(d for d in target_path.iterdir() if d.is_dir())
        for directory in candidates:
            if (
                (directory / "pyproject.toml").exists()
                or (directory / "requirements.txt").exists()
                or (directory / "composer.json").exists()
            ):
                domains.add("backend")
            if (directory / "package.json").exists():
                domains.add("frontend")
        return domains

    def _detect_pre_commit_hooks(self, target_path: Path) -> set[str]:
        config_path = target_path / ".pre-commit-config.yaml"
        if not config_path.exists():
            return set()
        data = yaml.safe_load(config_path.read_text()) or {}
        hook_ids: set[str] = set()
        for repo_entry in data.get("repos", []):
            for hook in repo_entry.get("hooks", []):
                if "id" in hook:
                    hook_ids.add(hook["id"])
        return hook_ids

    def _detect_husky_hooks(self, target_path: Path) -> set[str]:
        husky_dir = target_path / ".husky"
        package_json = target_path / "package.json"
        if not husky_dir.is_dir() or not package_json.exists():
            return set()
        data = json.loads(package_json.read_text())
        lint_staged = data.get("lint-staged", {})
        hook_ids: set[str] = set()
        for command_list in lint_staged.values():
            commands = command_list if isinstance(command_list, list) else [command_list]
            for command in commands:
                for hook_id in _HOOK_LOOKUP:
                    if hook_id in command:
                        hook_ids.add(hook_id)
        return hook_ids

    def _detect_lefthook_hooks(self, target_path: Path) -> set[str]:
        config_path = target_path / "lefthook.yml"
        if not config_path.exists():
            return set()
        data = yaml.safe_load(config_path.read_text()) or {}
        text = json.dumps(data)
        return {hook_id for hook_id in _HOOK_LOOKUP if hook_id in text}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_precommit_gate_runner.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/precommit_gate_runner.py tests/test_precommit_gate_runner.py
git commit -m "feat(radar-audit): add PreCommitGateRunner for criterion 2.4"
```

---

### Task 14: `normalize_precommit_gate` (criterion 2.4 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/precommit_gate.py`
- Test: `tests/test_normalize_precommit_gate.py`

**Interfaces:**
- Consumes: `RawToolOutput` shape from Task 13 (`pre-commit-gate`).
- Produces: `normalize_precommit_gate(session, scoring_run, criterion, tool_results) -> Score | None`. Archetype C (4-state): `tier == "none"` -> TODO -> 0.0; all applicable cells `True` -> DONE -> 10.0; some but not all `True` -> IN_PROGRESS -> `(covered/applicable)*10`; zero applicable cells (no domains detected at all) -> N/A -> `None`. One `Finding` per uncovered cell.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_precommit_gate.py
from radar_audit.normalizers.precommit_gate import normalize_precommit_gate
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence
from radar_core.models.audit import Audit, Repository, ToolResult
from radar_core.models.finding import Finding
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", clone_url="https://example.com/fixture.git")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Code quality", "Pre-commit quality gate")
    return audit, scoring_run, criterion


def test_scores_zero_when_tier_is_none(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="pre-commit-gate", tool_version="1.0.0", subproject_path=None,
        raw_output={"tier": "none", "domains": ["backend"], "cells": {}}, exit_code=0, duration_ms=5,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0


def test_scores_partial_and_adds_findings_for_uncovered_cells(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="pre-commit-gate", tool_version="1.0.0", subproject_path=None,
        raw_output={
            "tier": "pre-commit", "domains": ["backend"],
            "cells": {"backend:lint": True, "backend:type-check": False},
        },
        exit_code=0, duration_ms=5,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 5.0
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert len(findings) == 1
    assert findings[0].confidence == Confidence.HIGH


def test_confidence_is_low_when_lefthook_path_was_used(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="pre-commit-gate", tool_version="1.0.0", subproject_path=None,
        raw_output={
            "tier": "lefthook", "domains": ["backend"],
            "cells": {"backend:lint": True, "backend:type-check": False},
        },
        exit_code=0, duration_ms=5,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.LOW
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert findings[0].confidence == Confidence.LOW


def test_returns_none_when_no_domains_detected(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="pre-commit-gate", tool_version="1.0.0", subproject_path=None,
        raw_output={"tier": "none", "domains": [], "cells": {}}, exit_code=0, duration_ms=5,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [tool_result])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_precommit_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.precommit_gate'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/precommit_gate.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_VALIDATOR_TYPES = ("lint", "format", "type-check")


def normalize_precommit_gate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "pre-commit-gate" and r.exit_code == 0]
    if not relevant:
        return None

    tool_result = relevant[0]
    domains = tool_result.raw_output.get("domains", [])
    if not domains:
        return None

    # HIGH by default; LOW when the lefthook.yml detection path was used
    # (spec §7/§9 -- lefthook's hook-name-to-domain mapping is a heuristic).
    gate_confidence = (
        Confidence.LOW if tool_result.raw_output.get("tier") == "lefthook" else Confidence.HIGH
    )

    cells = tool_result.raw_output.get("cells", {})
    applicable = len(cells)
    if applicable == 0:
        value = 0.0
    else:
        covered = sum(1 for is_covered in cells.values() if is_covered)
        if covered == applicable:
            value = 10.0
        elif covered == 0:
            value = 0.0
        else:
            value = (covered / applicable) * 10

        for cell_key, is_covered in cells.items():
            if not is_covered:
                domain, validator_type = cell_key.split(":")
                session.add(
                    Finding(
                        scoring_run_id=scoring_run.id,
                        criterion_id=criterion.id,
                        tool_result_id=tool_result.id,
                        severity=FindingSeverity.LOW,
                        description=f"No pre-commit {validator_type} hook covers {domain}",
                        confidence=gate_confidence,
                        status=FindingStatus.OPEN,
                        human_verdict=HumanVerdict.UNREVIEWED,
                    )
                )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=gate_confidence,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_precommit_gate.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/normalizers/precommit_gate.py tests/test_normalize_precommit_gate.py
git commit -m "feat(radar-audit): add normalize_precommit_gate for criterion 2.4"
```

---

### Task 15: `JscpdRunner` (criterion 2.5, repo-scope)

**Files:**
- Create: `src/radar_audit/runners/jscpd_runner.py`
- Test: `tests/test_jscpd_runner.py`

**Interfaces:**
- Consumes: `RawToolOutput`.
- Produces: `JscpdRunner` (`tool_name="jscpd"`, `tool_version="1.0.0"`, `supported_stacks=frozenset()`, `scope="repo"`, `timeout_s=60`). Single cross-language pass over the whole repository tree via `npx --package=jscpd -- jscpd --reporters json --silent <target_path>`, excluding `node_modules`/`vendor`/`dist`/`build` (same exclusion convention as `dependency_cruiser_runner.py`'s `_ALWAYS_EXCLUDED_DIRNAMES`). `raw_output` shape: jscpd's native JSON report: `{"statistics": {"total": {"percentage": float, "duplicatedLines": int, "lines": int}}, "duplicates": [{"firstFile": {"name": str, "start": int, "end": int}, "secondFile": {"name": str, "start": int, "end": int}}]}`. Consumed by Task 16.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_jscpd_runner.py
from radar_audit.runners.jscpd_runner import JscpdRunner

from tests.git_helpers import init_git_repo

_UNIQUE_A = "export function add(a, b) {\n  return a + b;\n}\n"
_UNIQUE_B = "export function multiply(a, b) {\n  return a * b;\n}\n"

_DUPLICATE_BLOCK = "\n".join(f"  const line{i} = {i};" for i in range(20))
_DUPLICATE_A = f"export function first() {{\n{_DUPLICATE_BLOCK}\n  return 1;\n}}\n"
_DUPLICATE_B = f"export function second() {{\n{_DUPLICATE_BLOCK}\n  return 2;\n}}\n"


def test_reports_a_low_percentage_on_unique_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _UNIQUE_A, "src/b.js": _UNIQUE_B})

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["statistics"]["total"]["percentage"] < 5.0


def test_reports_duplicates_across_two_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _DUPLICATE_A, "src/b.js": _DUPLICATE_B})

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
    assert result.raw_output["statistics"]["total"]["percentage"] > 0.0


def test_excludes_node_modules_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _UNIQUE_A,
            "node_modules/pkg/a.js": _DUPLICATE_A,
            "node_modules/pkg/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    duplicate_files = {
        d["firstFile"]["name"] for d in result.raw_output["duplicates"]
    } | {d["secondFile"]["name"] for d in result.raw_output["duplicates"]}
    assert all("node_modules" not in name for name in duplicate_files)


def test_reports_tool_identity():
    runner = JscpdRunner()

    assert runner.tool_name == "jscpd"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_jscpd_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.jscpd_runner'`. When writing Step 3, run jscpd by hand against the duplicate fixture first and confirm the JSON report's exact key names (`statistics.total.percentage`, `duplicates[].firstFile.name`) — jscpd's report shape can vary by version; adjust the parsing before Step 4 if it differs.

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/runners/jscpd_runner.py
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")


class JscpdRunner:
    """Runs jscpd for cross-language code duplication detection (criterion 2.5)."""

    tool_name = "jscpd"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.TemporaryDirectory() as report_dir:
            ignore_patterns = [f"**/{name}/**" for name in _ALWAYS_EXCLUDED_DIRNAMES]
            for excluded in exclude_paths:
                ignore_patterns.append(f"{excluded}/**")

            command = [
                "npx", "--package=jscpd", "--", "jscpd",
                "--reporters", "json",
                "--output", report_dir,
                "--silent",
                "--ignore", ",".join(ignore_patterns),
                str(target_path),
            ]

            start = time.monotonic()
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout_s
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            report_path = Path(report_dir) / "jscpd-report.json"
            if not report_path.exists():
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )
            raw_output = json.loads(report_path.read_text())

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_jscpd_runner.py -v`
Expected: PASS (4 tests). First run in a fresh environment needs network access to fetch `jscpd` into the `npx` cache.

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/runners/jscpd_runner.py tests/test_jscpd_runner.py
git commit -m "feat(radar-audit): add JscpdRunner for criterion 2.5"
```

---

### Task 16: `normalize_code_duplication` (criterion 2.5 normalizer)

**Files:**
- Create: `src/radar_audit/normalizers/code_duplication.py`
- Test: `tests/test_normalize_code_duplication.py`

**Interfaces:**
- Consumes: `RawToolOutput` shape from Task 15 (`jscpd`).
- Produces: `normalize_code_duplication(session, scoring_run, criterion, tool_results) -> Score | None`. Bands per Global Constraints: ≤3%→10, 3-5%→6, 5-10%→4, >10%→2. Repo-scope, so at most one relevant `ToolResult` — no cross-subproject aggregation.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize_code_duplication.py
from radar_audit.normalizers.code_duplication import normalize_code_duplication
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, Repository, ToolResult
from radar_core.models.finding import Finding
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", clone_url="https://example.com/fixture.git")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Code quality", "Code duplication")
    return audit, scoring_run, criterion


def test_scores_ten_when_duplication_is_low(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="jscpd", tool_version="1.0.0", subproject_path=None,
        raw_output={"statistics": {"total": {"percentage": 1.2}}, "duplicates": []},
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_code_duplication(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_low_and_adds_findings_when_duplication_is_high(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id, tool_name="jscpd", tool_version="1.0.0", subproject_path=None,
        raw_output={
            "statistics": {"total": {"percentage": 15.0}},
            "duplicates": [
                {"firstFile": {"name": "a.js", "start": 1, "end": 20},
                 "secondFile": {"name": "b.js", "start": 1, "end": 20}},
            ],
        },
        exit_code=0, duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_code_duplication(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0
    findings = db_session.exec(select(Finding).where(Finding.scoring_run_id == scoring_run.id)).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_code_duplication(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_code_duplication.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.code_duplication'`

- [ ] **Step 3: Write the implementation**

```python
# src/radar_audit/normalizers/code_duplication.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Bands: <=3%->10, 3-5%->6, 5-10%->4, >10%->2 (spec §3.2). Resolved during
# design but provisional -- not yet calibrated against real portfolio data
# (spec §11), same discipline as 2.1's 30-line/400-LOC thresholds.
_BANDS: tuple[tuple[float, float], ...] = ((3.0, 10.0), (5.0, 6.0), (10.0, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_code_duplication(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "jscpd" and r.exit_code == 0]
    if not relevant:
        return None

    tool_result = relevant[0]
    percentage = tool_result.raw_output.get("statistics", {}).get("total", {}).get("percentage")
    if percentage is None:
        return None

    for duplicate in tool_result.raw_output.get("duplicates", []):
        first = duplicate["firstFile"]
        second = duplicate["secondFile"]
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=(
                    f"Duplicated block between {first['name']}:{first['start']}-{first['end']} "
                    f"and {second['name']}:{second['start']}-{second['end']}"
                ),
                file=first["name"],
                line=first["start"],
                confidence=Confidence.MEDIUM,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(percentage),
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(percentage: float) -> float:
    for max_percentage, value in _BANDS:
        if percentage <= max_percentage:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_code_duplication.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/radar_audit/normalizers/code_duplication.py tests/test_normalize_code_duplication.py
git commit -m "feat(radar-audit): add normalize_code_duplication for criterion 2.5"
```

---

### Task 17: Real-world validation against a portfolio repository

**Files:**
- Modify: none expected — this task's job is to run the whole category-2 pipeline against a real portfolio repository and fix whatever it surfaces, mirroring the three-bug fix wave that followed 2.1's own merge (see `project_radar_audit_phase4.md` memory).
- Test: none new — existing suites must stay green.

**Interfaces:**
- Consumes: every runner and normalizer from Tasks 1-16, the existing `radar-audit run` CLI, and `radar_audit.orchestrator`'s discovery/dispatch machinery (unchanged).
- Produces: a clean, meaningful `ScoringRun` with 5 category-2 `Score`s (or well-justified `None`s where a criterion is genuinely N/A for that repo) against a real portfolio repository, and any runner/normalizer fixes required to get there.

- [ ] **Step 1: Register the 11 new runners for dispatch**

Find wherever 2.1's five runners are registered for CLI dispatch (likely a runner list/registry in `src/radar_audit/orchestrator.py` or a dedicated `src/radar_audit/runners/__init__.py`) and add the 11 new runner instances from Tasks 1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 15 alongside them, following the exact same registration pattern already used for `DependencyCruiserRunner`, `PydepsRunner`, `DesignDocRunner`, `RadonModuleSizeRunner`, `StaticLocRunner`.

- [ ] **Step 2: Run the full existing test suite**

Run: `cd radar-audit && uv run pytest -v -m ""`
Expected: PASS, all tests from Tasks 1-16 plus every pre-existing 2.0/2.1 test green.

- [ ] **Step 3: Run a real audit against a portfolio repository**

Pick a real portfolio repo already used for 2.1's own validation (Summit-Stats — PHP/Laravel + Vue — or GeoChallenge-Tracker — Python/FastAPI + Vue). Run:

```bash
cd radar-audit && uv run radar-audit run <repo-name>
```

Then run the normalizers against the resulting `ToolResult`s (reuse the same manual-normalizer-invocation approach used for 2.1's own validation, since CLI wiring to normalizers is still out of scope per `project_radar_audit_phase4.md`'s open item) for all 5 category-2 criteria, and inspect the resulting `Score`/`Finding` rows for each.

- [ ] **Step 4: Fix whatever the real run surfaces**

Common classes of gaps to expect, based on 2.1's own real-world validation history: additional vendor/build directories not covered by `_SKIP_DIRNAMES`/`_ALWAYS_EXCLUDED_DIRNAMES`, a tool JSON shape that differs from what Tasks 1-16 assumed (Pint's fail-case shape, PHPStan's exact exit codes, PHPMD's exact exit codes, jscpd's exact report key names, ESLint 9 flat-config `-c` behavior), or a `PreCommitGateRunner` domain-detection miss for a repo's actual directory layout. Fix each in the relevant runner/normalizer, add a regression test capturing the real-world shape that was missed, and commit each fix separately with a `fix(radar-audit): <specific bug>` message.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(radar-audit): register category 2 runners and validate against a real portfolio repo"
```
