# Category-Level Scoring and Report Pipeline (Scope A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-existing category 1-3 normalizers into a real, re-runnable `radar-audit score <repo>` command that produces `Score` rows (CRITERION + CATEGORY level), and a `radar-audit report <repo>` command that renders a per-repo Markdown progress report showing real scores for categories 1-3 and explicit "Not yet audited" placeholders for categories 4-15.

**Architecture:** Three independent, idempotent CLI commands (`run` → `score` → `report`), each operating purely against the DB (no repo checkout needed for `score`/`report`). A new criterion→normalizer registry in `normalizers/__init__.py` drives both the scoring step and the report's "not yet tooled" detection. No `ToolRunner`/schema/migration changes.

**Tech Stack:** Python 3.12, SQLModel, Typer, pytest — same stack as every prior increment, no new dependency.

**Spec:** `docs/superpowers/specs/2026-09-22-scoring-and-report-pipeline-design.md`

## Global Constraints

- No `ToolRunner` protocol changes, no `Score`/`ScoringRun`/`Criterion`/`Category` schema changes, no new Alembic migration.
- `score` and `report` are new Typer commands in `radar-audit/src/radar_audit/cli.py`, following the same `_database_url()`/session-open-close-dispose pattern as the existing `run` command, and adding their new error types to the `_EXPECTED_ERRORS` tuple so failures print a clean one-line error, never a traceback.
- `score`/`report` never require the target repo to be checked out on disk — both resolve the `Repository` row by name directly from the DB and operate purely against already-persisted rows.
- Category-level weight redistribution is a simple renormalization over scored criteria only (`weighted_sum / total_weight` computed just over the criteria that got a `Score` this run) — no distinction between "structurally not tooled" (1.4, 3.5) and "tooled but returned `N/A` this run" is made anywhere in this plan.
- Re-running `score` against the same `Audit` must not duplicate `Score` rows: delete every existing `Score` row for the reused `ScoringRun` before regenerating, the same delete-then-recreate idempotency pattern `orchestrator.execute_audit` already uses for `ToolResult`.
- Report output directory defaults to `radar-audit/reports/` (`Path(__file__).resolve().parents[2] / "reports"` in `cli.py` — the exact same anchor `DEFAULT_PORTFOLIO_YAML` already uses), gitignored, never hand-edited or committed.
- Tests use real SQLite fixtures via the existing `db_session` fixture (`tests/conftest.py`) — no mocking of DB state, same "zero mock" discipline as every prior increment.
- Confidence ranking for the "lowest of contributors" rule: `HIGH` < `MEDIUM` < `LOW` in severity (i.e. `LOW` is the worst/lowest confidence and wins when present among a category's contributing criteria).

---

### Task 1: Normalizer registry

**Files:**
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (currently empty)
- Test: `radar-audit/tests/test_normalizer_registry.py`

**Interfaces:**
- Consumes: the 12 existing normalizer functions (`normalize_dependency_circularity`, `normalize_design_doc`, `normalize_module_size`, `normalize_lint_pass_rate`, `normalize_type_check_pass_rate`, `normalize_cyclomatic_complexity`, `normalize_precommit_gate`, `normalize_code_duplication`, `normalize_unit_test_pass_rate`, `normalize_integration_tests`, `normalize_e2e_tests`, `normalize_ci_test_execution`), all already implemented under `radar_audit.normalizers.*`. `get_criterion`/`seed_taxonomy` (existing, `normalizers/shared.py` and `taxonomy/seed.py`).
- Produces: `CRITERION_NORMALIZERS: dict[tuple[str, str], NormalizerFn]` and `NormalizerFn` type alias, both importable from `radar_audit.normalizers`. Task 2's `scoring.py` consumes both by name.

- [x] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_normalizer_registry.py
from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import get_criterion
from radar_audit.taxonomy.seed import seed_taxonomy


def test_registry_has_exactly_the_twelve_tooled_criteria():
    assert len(CRITERION_NORMALIZERS) == 12


def test_registry_excludes_the_two_deferred_llm_judgment_criteria():
    assert ("Architecture & design", "Consistency of architectural style") not in CRITERION_NORMALIZERS
    assert ("Testing & reliability", "Test quality / relevance") not in CRITERION_NORMALIZERS


def test_every_registry_key_resolves_to_a_seeded_criterion(db_session):
    methodology_version = seed_taxonomy(db_session)

    for category_name, criterion_name in CRITERION_NORMALIZERS:
        criterion = get_criterion(db_session, methodology_version.id, category_name, criterion_name)
        assert criterion.name == criterion_name


def test_every_registry_value_is_callable():
    for normalizer in CRITERION_NORMALIZERS.values():
        assert callable(normalizer)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalizer_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'CRITERION_NORMALIZERS' from 'radar_audit.normalizers'`

- [x] **Step 3: Write the implementation**

```python
# radar-audit/src/radar_audit/normalizers/__init__.py
from __future__ import annotations

from collections.abc import Callable

from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.ci_test_execution import normalize_ci_test_execution
from radar_audit.normalizers.code_duplication import normalize_code_duplication
from radar_audit.normalizers.cyclomatic_complexity import normalize_cyclomatic_complexity
from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.e2e_tests import normalize_e2e_tests
from radar_audit.normalizers.integration_tests import normalize_integration_tests
from radar_audit.normalizers.lint_pass_rate import normalize_lint_pass_rate
from radar_audit.normalizers.module_size import normalize_module_size
from radar_audit.normalizers.precommit_gate import normalize_precommit_gate
from radar_audit.normalizers.type_check_pass_rate import normalize_type_check_pass_rate
from radar_audit.normalizers.unit_test_pass_rate import normalize_unit_test_pass_rate

NormalizerFn = Callable[[Session, ScoringRun, Criterion, list[ToolResult]], Score | None]

CRITERION_NORMALIZERS: dict[tuple[str, str], NormalizerFn] = {
    ("Architecture & design", "Dependency direction / circularity"): normalize_dependency_circularity,
    ("Architecture & design", "Architectural documentation present"): normalize_design_doc,
    ("Architecture & design", "Module size distribution"): normalize_module_size,
    ("Code quality", "Linter clean pass rate"): normalize_lint_pass_rate,
    ("Code quality", "Type-checking pass"): normalize_type_check_pass_rate,
    ("Code quality", "Cyclomatic complexity"): normalize_cyclomatic_complexity,
    ("Code quality", "Pre-commit quality gate"): normalize_precommit_gate,
    ("Code quality", "Code duplication"): normalize_code_duplication,
    ("Testing & reliability", "Unit tests present & passing, with coverage"): normalize_unit_test_pass_rate,
    ("Testing & reliability", "Integration tests"): normalize_integration_tests,
    ("Testing & reliability", "E2E tests"): normalize_e2e_tests,
    ("Testing & reliability", "CI executes the test suite"): normalize_ci_test_execution,
}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalizer_registry.py -v`
Expected: PASS (4 passed)

- [x] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalizer_registry.py
git commit -m "feat(radar-audit): add criterion-to-normalizer registry for categories 1-3"
```

---

### Task 2: `score_repository` — criterion + category scoring

**Files:**
- Create: `radar-audit/src/radar_audit/scoring.py`
- Test: `radar-audit/tests/test_scoring.py`

**Interfaces:**
- Consumes: `CRITERION_NORMALIZERS` (Task 1). `get_criterion`, `get_or_create_scoring_run` (`radar_audit.normalizers.shared`, existing). `seed_taxonomy` (`radar_audit.taxonomy.seed`, existing). `Repository` (`radar_core.models.repository`), `Audit`, `ToolResult` (`radar_core.models.audit`), `Category`, `Criterion` (`radar_core.models.methodology`), `Score`, `ScoringRun` (`radar_core.models.scoring`), `ScoreLevel`, `Confidence` (`radar_core.enums`) — all existing.
- Produces: `score_repository(session: Session, repo_name: str) -> ScoringRun`, `RepositoryNotFoundError(ValueError)`, `NoAuditFoundError(ValueError)`, `get_repository_by_name(session: Session, repo_name: str) -> Repository`. Task 3 (`report.py`) and Task 4 (CLI) consume all four names from `radar_audit.scoring`.

- [x] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_scoring.py
import pytest
from radar_audit.config import PortfolioConfig
from radar_audit.orchestrator import execute_audit
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.normalizers.shared import get_criterion
from radar_audit.scoring import (
    NoAuditFoundError,
    RepositoryNotFoundError,
    score_repository,
)
from radar_core.enums import ScoreLevel
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score
from sqlmodel import select

from tests.git_helpers import init_git_repo


def _audited_repo(db_session, tmp_path, name="repo", files=None):
    repo_path = tmp_path / name
    init_git_repo(repo_path, files=files or {})
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    return execute_audit(db_session, config, name, DEFAULT_RUNNERS)


def test_score_repository_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError, match="does-not-exist"):
        score_repository(db_session, "does-not-exist")


def test_score_repository_raises_when_no_audit_exists(db_session):
    from radar_core.models.repository import Repository

    db_session.add(Repository(name="unaudited", path="/tmp/unaudited"))
    db_session.commit()

    with pytest.raises(NoAuditFoundError, match="unaudited"):
        score_repository(db_session, "unaudited")


def test_score_repository_creates_criterion_and_category_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    criterion_scores = [s for s in scores if s.level == ScoreLevel.CRITERION]
    category_scores = [s for s in scores if s.level == ScoreLevel.CATEGORY]

    assert len(criterion_scores) >= 1
    assert len(category_scores) >= 1
    assert all(0.0 <= s.value <= 10.0 for s in category_scores)


def test_score_repository_is_idempotent_no_duplicate_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"},
    )

    first_run = score_repository(db_session, "repo")
    first_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == first_run.id)).all()
    )

    second_run = score_repository(db_session, "repo")
    second_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == second_run.id)).all()
    )

    assert first_run.id == second_run.id
    assert first_count == second_count


def test_category_score_redistributes_weight_over_scored_criteria_only(db_session, tmp_path):
    # Architecture & design has 4 criteria at weight 25.0 each, but only 3 are
    # ever scored (1.4 has no normalizer). Equal weights mean the redistributed
    # weighted average reduces to a plain average of exactly those 3 -- not a
    # naive /4 average that would silently treat the missing one as a zero.
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")
    methodology_version_id = scoring_run.methodology_version_id
    arch_criterion = get_criterion(
        db_session, methodology_version_id, "Architecture & design", "Dependency direction / circularity"
    )
    arch_criterion_ids = {
        c.id
        for c in db_session.exec(
            select(Criterion).where(Criterion.category_id == arch_criterion.category_id)
        ).all()
    }

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    arch_criterion_scores = [
        s for s in scores if s.level == ScoreLevel.CRITERION and s.criterion_id in arch_criterion_ids
    ]
    arch_category_score = next(
        s
        for s in scores
        if s.level == ScoreLevel.CATEGORY and s.category_id == arch_criterion.category_id
    )

    assert len(arch_criterion_scores) == 3
    expected = sum(s.value for s in arch_criterion_scores) / len(arch_criterion_scores)
    assert arch_category_score.value == pytest.approx(expected)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.scoring'`

- [x] **Step 3: Write the implementation**

```python
# radar-audit/src/radar_audit/scoring.py
from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session, select

from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


class RepositoryNotFoundError(ValueError):
    """Raised when no Repository row exists for the given name."""


class NoAuditFoundError(ValueError):
    """Raised when a Repository has no Audit row yet."""


def get_repository_by_name(session: Session, repo_name: str) -> Repository:
    repository = session.exec(select(Repository).where(Repository.name == repo_name)).first()
    if repository is None:
        raise RepositoryNotFoundError(
            f"No repository named {repo_name!r} -- run 'radar-audit run {repo_name}' first"
        )
    return repository


def _get_latest_audit(session: Session, repository: Repository) -> Audit:
    audit = session.exec(
        select(Audit)
        .where(Audit.repository_id == repository.id)
        .order_by(Audit.audited_at.desc())
    ).first()
    if audit is None:
        raise NoAuditFoundError(
            f"No audit found for {repository.name!r} -- run 'radar-audit run {repository.name}' first"
        )
    return audit


def score_repository(session: Session, repo_name: str) -> ScoringRun:
    repository = get_repository_by_name(session, repo_name)
    audit = _get_latest_audit(session, repository)
    methodology_version = seed_taxonomy(session)
    scoring_run = get_or_create_scoring_run(session, audit, methodology_version)

    existing_scores = session.exec(
        select(Score).where(Score.scoring_run_id == scoring_run.id)
    ).all()
    for existing in existing_scores:
        session.delete(existing)
    session.commit()

    tool_results = session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()

    scored_by_category: dict[int, list[tuple[Criterion, Score]]] = {}
    for (category_name, criterion_name), normalizer in CRITERION_NORMALIZERS.items():
        criterion = get_criterion(session, methodology_version.id, category_name, criterion_name)
        score = normalizer(session, scoring_run, criterion, tool_results)
        if score is None:
            continue
        scored_by_category.setdefault(criterion.category_id, []).append((criterion, score))

    for category_id, pairs in scored_by_category.items():
        category = session.get(Category, category_id)
        assert category is not None
        _write_category_score(session, scoring_run, category, pairs)

    return scoring_run


def _write_category_score(
    session: Session,
    scoring_run: ScoringRun,
    category: Category,
    pairs: list[tuple[Criterion, Score]],
) -> Score:
    total_weight = sum(criterion.weight for criterion, _ in pairs)
    weighted_sum = sum(criterion.weight * score.value for criterion, score in pairs)
    value = weighted_sum / total_weight
    confidence = max((score.confidence for _, score in pairs), key=lambda c: _CONFIDENCE_RANK[c])

    category_score = Score(
        scoring_run_id=scoring_run.id,
        category_id=category.id,
        level=ScoreLevel.CATEGORY,
        value=value,
        confidence=confidence,
    )
    session.add(category_score)
    session.commit()
    session.refresh(category_score)
    return category_score
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_scoring.py -v`
Expected: PASS (5 passed)

- [x] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/scoring.py radar-audit/tests/test_scoring.py
git commit -m "feat(radar-audit): add score_repository with category-level weighted aggregation"
```

---

### Task 3: `render_report` / `write_report`

**Files:**
- Create: `radar-audit/src/radar_audit/report.py`
- Test: `radar-audit/tests/test_report.py`

**Interfaces:**
- Consumes: `get_repository_by_name`, `RepositoryNotFoundError` (Task 2, `radar_audit.scoring`). `Audit` (`radar_core.models.audit`), `Category`, `Criterion` (`radar_core.models.methodology`), `Score`, `ScoringRun` (`radar_core.models.scoring`), `ScoreLevel` (`radar_core.enums`) — all existing.
- Produces: `render_report(session: Session, repo_name: str) -> str`, `write_report(markdown: str, repo_name: str, output_dir: Path) -> Path`, `NoScoringRunFoundError(ValueError)`. Task 5 (CLI) consumes all three from `radar_audit.report`.

- [x] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_report.py
import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.orchestrator import execute_audit
from radar_audit.report import NoScoringRunFoundError, render_report, write_report
from radar_audit.scoring import RepositoryNotFoundError, score_repository

from tests.git_helpers import init_git_repo


def _scored_repo(db_session, tmp_path, name="repo"):
    repo_path = tmp_path / name
    init_git_repo(
        repo_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    execute_audit(db_session, config, name, DEFAULT_RUNNERS)
    return score_repository(db_session, name)


def test_render_report_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError):
        render_report(db_session, "does-not-exist")


def test_render_report_raises_when_no_score_exists(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    with pytest.raises(NoScoringRunFoundError):
        render_report(db_session, "repo")


def test_render_report_shows_scored_categories_and_not_yet_audited_placeholders(db_session, tmp_path):
    _scored_repo(db_session, tmp_path)

    markdown = render_report(db_session, "repo")

    assert "# Report: repo" in markdown
    assert "Architecture & design" in markdown
    assert "Not yet audited" in markdown  # category 4 (Security) has no data yet
    assert "not scored this run" in markdown  # 1.4 has no normalizer


def test_write_report_creates_file_under_repo_named_subdir(db_session, tmp_path):
    _scored_repo(db_session, tmp_path)
    markdown = render_report(db_session, "repo")

    output_dir = tmp_path / "reports"
    written_path = write_report(markdown, "repo", output_dir)

    assert written_path == output_dir / "repo" / "latest.md"
    assert written_path.read_text() == markdown
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.report'`

- [x] **Step 3: Write the implementation**

```python
# radar-audit/src/radar_audit/report.py
from __future__ import annotations

from pathlib import Path

from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session, select

from radar_audit.scoring import get_repository_by_name


class NoScoringRunFoundError(ValueError):
    """Raised when a Repository has no ScoringRun row yet."""


def _get_latest_scoring_run(session: Session, repository_id: int, repository_name: str) -> ScoringRun:
    scoring_run = session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(ScoringRun.scored_at.desc())
    ).first()
    if scoring_run is None:
        raise NoScoringRunFoundError(
            f"No score found for {repository_name!r} -- run 'radar-audit score {repository_name}' first"
        )
    return scoring_run


def render_report(session: Session, repo_name: str) -> str:
    repository = get_repository_by_name(session, repo_name)
    scoring_run = _get_latest_scoring_run(session, repository.id, repository.name)
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None

    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    scores = session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_scores = {s.category_id: s for s in scores if s.level == ScoreLevel.CATEGORY}
    criterion_scores = {s.criterion_id: s for s in scores if s.level == ScoreLevel.CRITERION}

    lines = [
        f"# Report: {repository.name}",
        "",
        f"- Commit: `{audit.commit_sha}`",
        f"- Audited at: {audit.audited_at.isoformat()}",
        f"- Scored at: {scoring_run.scored_at.isoformat()}",
        "",
    ]

    for category in categories:
        category_score = category_scores.get(category.id)

        if category_score is None:
            lines.append(f"## {category.order}. {category.name} -- Not yet audited")
            lines.append("")
            continue

        lines.append(
            f"## {category.order}. {category.name} -- {category_score.value:.1f}/10 "
            f"({category_score.confidence.value} confidence)"
        )
        criteria = session.exec(
            select(Criterion)
            .where(Criterion.category_id == category.id)
            .order_by(Criterion.id)  # type: ignore[arg-type]
        ).all()
        for criterion in criteria:
            criterion_score = criterion_scores.get(criterion.id)
            if criterion_score is None:
                lines.append(f"- {criterion.name}: not scored this run")
            else:
                lines.append(f"- {criterion.name}: {criterion_score.value:.1f}/10")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(markdown: str, repo_name: str, output_dir: Path) -> Path:
    target_dir = output_dir / repo_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "latest.md"
    target_path.write_text(markdown)
    return target_path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_report.py -v`
Expected: PASS (4 passed)

- [x] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/report.py radar-audit/tests/test_report.py
git commit -m "feat(radar-audit): add render_report/write_report for per-repo Markdown output"
```

---

### Task 4: CLI `score` command

**Files:**
- Modify: `radar-audit/src/radar_audit/cli.py`
- Test: `radar-audit/tests/test_cli_score_report.py`

**Interfaces:**
- Consumes: `score_repository`, `RepositoryNotFoundError`, `NoAuditFoundError` (Task 2, `radar_audit.scoring`).
- Produces: `radar-audit score <repo>` Typer command, exit code 0 on success, 1 with a clean `Error: ...` line (no traceback) on `RepositoryNotFoundError`/`NoAuditFoundError`.

- [x] **Step 1: Write the failing tests**

```python
# radar-audit/tests/test_cli_score_report.py
from radar_audit.cli import app
from typer.testing import CliRunner

from tests.conftest import RADAR_CORE_ROOT
from tests.git_helpers import init_git_repo

runner = CliRunner()


def _migrate(db_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")
    alembic_config = Config(str(RADAR_CORE_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(RADAR_CORE_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")


def _write_config(tmp_path, repos_root, repo_names):
    path = tmp_path / "portfolio.yaml"
    repos_yaml = "\n".join(f"  - name: {name}" for name in repo_names)
    path.write_text(f"repos_root: {repos_root}\nrepositories:\n{repos_yaml}\n")
    return path


def test_score_command_fails_cleanly_for_unknown_repo(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    result = runner.invoke(app, ["score", "not-a-real-repo"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "Error:" in result.stderr
    assert "not-a-real-repo" in result.stderr


def test_score_command_persists_scores_for_an_audited_repo(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path, files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"})
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    run_result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])
    assert run_result.exit_code == 0

    score_result = runner.invoke(app, ["score", "sample-repo"])
    assert score_result.exit_code == 0

    from radar_core.db import get_engine
    from radar_core.enums import ScoreLevel
    from radar_core.models.scoring import Score
    from sqlmodel import Session, select

    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        scores = session.exec(select(Score)).all()
        assert any(s.level == ScoreLevel.CRITERION for s in scores)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_cli_score_report.py -v`
Expected: FAIL with `typer.testing` reporting `No such command 'score'` / non-zero unexpected exit code

- [x] **Step 3: Write the implementation**

Edit `radar-audit/src/radar_audit/cli.py`:

```python
# add to the import block near the top, alongside the existing radar_audit imports
from radar_audit.scoring import NoAuditFoundError, RepositoryNotFoundError, score_repository
```

```python
# extend _EXPECTED_ERRORS
_EXPECTED_ERRORS = (
    MissingDatabaseUrlError,
    PortfolioConfigError,
    FileNotFoundError,
    CalledProcessError,
    RepositoryNotFoundError,
    NoAuditFoundError,
)
```

```python
# new command, placed after `run`
@app.command()
def score(
    repo_name: str = typer.Argument(..., help="Repository name (must already have an audit)"),
) -> None:
    try:
        engine = get_engine(_database_url())
        session = get_session(engine)
        try:
            score_repository(session, repo_name)
        finally:
            session.close()
            engine.dispose()
    except _EXPECTED_ERRORS as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_cli_score_report.py -v`
Expected: PASS (2 passed)

- [x] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/cli.py radar-audit/tests/test_cli_score_report.py
git commit -m "feat(radar-audit): add 'radar-audit score' CLI command"
```

---

### Task 5: CLI `report` command + gitignore

**Files:**
- Modify: `radar-audit/src/radar_audit/cli.py`
- Modify: `.gitignore` (repo root)
- Modify: `radar-audit/tests/test_cli_score_report.py`

**Interfaces:**
- Consumes: `render_report`, `write_report`, `NoScoringRunFoundError` (Task 3, `radar_audit.report`).
- Produces: `radar-audit report <repo> [--output-dir PATH]` Typer command, writes `<output_dir>/<repo>/latest.md`, prints the written path, exit code 0 on success, 1 with a clean error on `RepositoryNotFoundError`/`NoScoringRunFoundError`.

- [x] **Step 1: Write the failing tests**

Append to `radar-audit/tests/test_cli_score_report.py`:

```python
def test_report_command_fails_cleanly_when_not_scored_yet(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    run_result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])
    assert run_result.exit_code == 0

    report_result = runner.invoke(app, ["report", "sample-repo"])

    assert report_result.exit_code == 1
    assert "Error:" in report_result.stderr
    assert "sample-repo" in report_result.stderr


def test_report_command_writes_markdown_to_output_dir(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(
        repo_path,
        files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"},
    )
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    assert runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)]).exit_code == 0
    assert runner.invoke(app, ["score", "sample-repo"]).exit_code == 0

    output_dir = tmp_path / "reports"
    report_result = runner.invoke(
        app, ["report", "sample-repo", "--output-dir", str(output_dir)]
    )

    assert report_result.exit_code == 0
    written = output_dir / "sample-repo" / "latest.md"
    assert written.exists()
    assert "# Report: sample-repo" in written.read_text()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_cli_score_report.py -v`
Expected: FAIL — `No such command 'report'`

- [x] **Step 3: Write the implementation**

Edit `radar-audit/src/radar_audit/cli.py`:

```python
# add to the import block
from radar_audit.report import NoScoringRunFoundError, render_report, write_report
```

```python
# extend _EXPECTED_ERRORS
_EXPECTED_ERRORS = (
    MissingDatabaseUrlError,
    PortfolioConfigError,
    FileNotFoundError,
    CalledProcessError,
    RepositoryNotFoundError,
    NoAuditFoundError,
    NoScoringRunFoundError,
)
```

```python
# add near the other DEFAULT_* module constants
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"
```

```python
# new command, placed after `score`
@app.command()
def report(
    repo_name: str = typer.Argument(..., help="Repository name (must already have a score)"),
    output_dir: Path = typer.Option(  # noqa: B008
        DEFAULT_REPORTS_DIR, "--output-dir", help="Directory to write the report into"
    ),
) -> None:
    try:
        engine = get_engine(_database_url())
        session = get_session(engine)
        try:
            markdown = render_report(session, repo_name)
            written_path = write_report(markdown, repo_name, output_dir)
            typer.echo(f"Report written to {written_path}")
        finally:
            session.close()
            engine.dispose()
    except _EXPECTED_ERRORS as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc
```

Edit `.gitignore` (repo root), adding alongside the existing `*.db` entry:

```
radar-audit/reports/
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_cli_score_report.py -v`
Expected: PASS (4 passed)

- [x] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/cli.py radar-audit/tests/test_cli_score_report.py .gitignore
git commit -m "feat(radar-audit): add 'radar-audit report' CLI command, gitignore generated reports"
```

---

### Task 6: Full test suite, lint/type gates, and real-repo validation

**Files:** none created — validation only, per this project's established discipline of confirming plausibility against a real portfolio repo before an increment is considered done.

- [x] **Step 1: Run the full radar-audit test suite**

Run: `cd radar-audit && uv run pytest -v`
Expected: PASS, no regressions in any pre-existing test file.

- [x] **Step 2: Run lint and type checks**

Run: `cd radar-audit && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: no findings.

- [x] **Step 3: Real-repo end-to-end validation**

Run against an actual portfolio repo (Python+Vue: GeoChallenge-Tracker), using a throwaway database:

```bash
cd radar-audit
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_scoring_validation_XXXX.db)"
uv run radar-audit run GeoChallenge-Tracker
uv run radar-audit score GeoChallenge-Tracker
uv run radar-audit report GeoChallenge-Tracker --output-dir /tmp/radar_reports_validation
cat /tmp/radar_reports_validation/GeoChallenge-Tracker/latest.md
unset RADAR_DATABASE_URL
```

Inspect the printed report: categories 1-3 must show plausible, non-`None` numeric scores (0-10 range) with per-criterion detail; 1.4 and 3.5 must render as "not scored this run"; categories 4-15 must all render as "Not yet audited". Report any implausible score before considering the task done (e.g. a category score outside 0-10, a crash on a real repo's tool output shape that no synthetic fixture exercised).

- [x] **Step 4: Update the plan file to mark every task complete, commit**

```bash
git add docs/superpowers/plans/2026-09-22-scoring-and-report-pipeline.md
git commit -m "docs(radar-audit): mark scoring and report pipeline plan complete"
```
