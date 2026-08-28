# Category 1 (Architecture & Design) Runners Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the throwaway `ExampleGitLogRunner` with five real, tested `ToolRunner` implementations covering Quality Framework category 1 criteria 1.1-1.3 (dependency circularity, architectural documentation presence, module size distribution), plus their raw-output normalizers, establishing the criterion-level `Finding`/`Score` pattern that increments 2.2-2.15 will each repeat.

**Architecture:** `radar-audit` gains a `ToolResult.subproject_path` column (new Alembic migration) and a `ToolRunner` protocol extended with `supported_stacks`/`scope`/`timeout_s`, so the orchestrator can filter runners by stack and dedupe repo-scoped runners across sub-projects. Five new runner classes shell out to `dependency-cruiser`, `pydeps`, `radon`, or do a pure filesystem walk/check, each producing a `RawToolOutput`. Three normalizer functions read persisted `ToolResult` rows and write `Finding`/`Score` rows at `ScoreLevel.CRITERION` for a `ScoringRun`.

**Tech Stack:** Python 3.12, SQLModel/Alembic (radar-core), Typer CLI, `subprocess` + `npx --package=dependency-cruiser` / `uvx pydeps` / `uvx radon`, pytest with real subprocess invocations (no mocking).

**Spec:** `docs/superpowers/specs/2026-08-28-radar-audit-category-1-architecture-design.md`

**Deviation from spec, verified empirically before writing this plan:** §6 of the spec says `PydepsRunner` invokes `uvx pydeps <target_path> --show-cycles --no-output`. Live testing (this session) showed `--show-cycles` produces **no stdout output at all**, even against a fixture with a genuine import cycle. This plan instead uses `uvx pydeps <target_path> --show-deps --no-output --max-bacon=0`, confirmed to reliably return a structured JSON import graph (`{"module.name": {"imports": [...], "imported_by": [...], ...}}`). Cycle detection runs in the normalizer (Task 10) as a DFS over each module's `imports` adjacency list, not via any tool-reported "cycle" text.

**Known limitation, not solved by this increment (documented, not a placeholder):** `PydepsRunner`'s cycle detection is only accurate when the `target_path` handed to it by the orchestrator (a discovered sub-project root) is itself an importable Python package root (contains `__init__.py`, and its own directory name matches the import style used by the code inside it, e.g. `from app import b` requires `target_path` to literally be the `app/` directory). Real repos where the manifest (`pyproject.toml`) lives one level above the actual package will get a `ToolResult` with a valid but internally-disconnected import graph (pydeps can't resolve the package's own absolute imports), which under-reports cycles rather than crashing. Same class of accepted imprecision as 1.3's "LOC is a weak modularity proxy" — not addressed here, no package-root auto-detection is in scope.

## Global Constraints

- New Alembic migration for `ToolResult.subproject_path`, chained after `555ffc592f67` (current head).
- `ToolRunner` protocol changes (`supported_stacks`, `scope`, `timeout_s`) are binding for all five new runners; no runner keeps the old two-field-only shape.
- Every `npx` invocation pins its package explicitly (`--package=<exact-name> --`), per the dependency-confusion near-miss in `toolchain.md` — never a bare binary name.
- Tests use real `npx`/`uvx`/`radon` invocations against `tmp_path` git fixtures (`init_git_repo`) — no mocking of subprocess or tool output.
- `Score` rows this increment writes are `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is ever created here.
- Provisional numeric thresholds (1.2's 30-line minimum, 1.3's 400-LOC "covered" cutoff) are marked provisional in code comments, not presented as calibrated values.
- Missing-data handling: a `ToolResult` with a non-zero/`-1` `exit_code` produces no `Finding` and no `Score` for that criterion/sub-project.
- Multi-sub-project aggregation: worst-band-wins for criterion 1.1 (Archetype A), summed-ratio for criterion 1.3 (Archetype B).

---

### Task 1: `ToolResult.subproject_path` column

**Files:**
- Modify: `radar-core/src/radar_core/models/audit.py:37-51`
- Create: `radar-core/alembic/versions/397586186d42_add_subproject_path_to_tool_result.py`
- Test: `radar-core/tests/models/test_audit.py:15-37`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ToolResult.subproject_path: str` — every later task that constructs a `ToolResult` (Task 3's orchestrator, any test fixture) must supply it.

- [ ] **Step 1: Write the failing test**

Modify `radar-core/tests/models/test_audit.py`'s `test_create_audit_with_tool_result`:

```python
def test_create_audit_with_tool_result(db_session):
    repo = _make_repository(db_session)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="gitleaks",
        tool_version="8.18.0",
        command="gitleaks detect --report-format json",
        raw_output={"findings": []},
        exit_code=0,
        duration_ms=420,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)

    assert tool_result.audit_id == audit.id
    assert tool_result.subproject_path == "."
    assert tool_result.raw_output == {"findings": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-core && uv run pytest tests/models/test_audit.py::test_create_audit_with_tool_result -v`
Expected: FAIL with `TypeError: 'subproject_path' is an invalid keyword argument` (field doesn't exist yet on the model).

- [ ] **Step 3: Add the field to the model**

In `radar-core/src/radar_core/models/audit.py`, add the new field right after `audit_id` on `ToolResult`:

```python
class ToolResult(SQLModel, table=True):
    __tablename__ = "tool_result"

    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(foreign_key="audit.id", index=True)
    subproject_path: str = Field(index=True)
    tool_name: str = Field(index=True)
    tool_version: str
    command: str
    raw_output: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    exit_code: int
    ran_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )
    duration_ms: int
```

- [ ] **Step 4: Write the Alembic migration**

Create `radar-core/alembic/versions/397586186d42_add_subproject_path_to_tool_result.py`:

```python
"""add subproject_path to tool_result

Revision ID: 397586186d42
Revises: 555ffc592f67
Create Date: 2026-08-28 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "397586186d42"
down_revision = "555ffc592f67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tool_result", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "subproject_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            )
        )
        batch_op.create_index(
            batch_op.f("ix_tool_result_subproject_path"), ["subproject_path"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("tool_result", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tool_result_subproject_path"))
        batch_op.drop_column("subproject_path")
```

Note: no rows exist in any real database yet (increment 2.0 only ran the throwaway example against test fixtures), so `nullable=False` with no default is safe here — no backfill step needed.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd radar-core && uv run pytest tests/models/test_audit.py -v`
Expected: PASS (all tests in the file, including the ones that don't touch `subproject_path`, since `conftest.py`'s `db_session` fixture runs migrations fresh per test).

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/audit.py \
        radar-core/alembic/versions/397586186d42_add_subproject_path_to_tool_result.py \
        radar-core/tests/models/test_audit.py
git commit -m "feat(radar-core): add subproject_path to ToolResult"
```

---

### Task 2: `ToolRunner` protocol extension

**Files:**
- Modify: `radar-audit/src/radar_audit/runner.py:1-20`
- Modify: `radar-audit/src/radar_audit/runners/example.py`
- Test: `radar-audit/tests/test_runner.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ToolRunner` Protocol with `supported_stacks: frozenset[str]`, `scope: Literal["repo", "subproject"]`, `timeout_s: int`, and `run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput`. Every runner task from here on (Tasks 4-8) implements this exact shape.

- [ ] **Step 1: Write the failing test**

Add to `radar-audit/tests/test_runner.py`:

```python
def test_example_runner_declares_protocol_metadata():
    runner = ExampleGitLogRunner()

    assert runner.supported_stacks == frozenset({"unknown", "python", "javascript", "php"})
    assert runner.scope == "subproject"
    assert runner.timeout_s == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_runner.py::test_example_runner_declares_protocol_metadata -v`
Expected: FAIL with `AttributeError: 'ExampleGitLogRunner' object has no attribute 'supported_stacks'`.

- [ ] **Step 3: Extend the protocol and update `ExampleGitLogRunner`**

Replace `radar-audit/src/radar_audit/runner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True)
class RawToolOutput:
    command: str
    raw_output: dict[str, object]
    exit_code: int
    duration_ms: int


class ToolRunner(Protocol):
    tool_name: str
    tool_version: str
    supported_stacks: frozenset[str]
    scope: Literal["repo", "subproject"]
    timeout_s: int

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput: ...
```

Replace `radar-audit/src/radar_audit/runners/example.py`:

```python
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class ExampleGitLogRunner:
    """Throwaway proof-of-pipeline runner. Removed once the real category-1 runners land."""

    tool_name = "example-git-log"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"unknown", "python", "javascript", "php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["git", "-C", str(target_path), "log", "-1", "--format=%H"]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

The existing `test_example_runner_reports_head_commit_sha` and `test_example_runner_nonzero_exit_on_non_git_directory` tests call `runner.run(repo_path, exclude_paths=[])` positionally, so the parameter rename from `subproject_path` to `target_path` doesn't break them.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_runner.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runner.py radar-audit/src/radar_audit/runners/example.py \
        radar-audit/tests/test_runner.py
git commit -m "feat(radar-audit): extend ToolRunner protocol with stack/scope/timeout"
```

---

### Task 3: Orchestrator scope/stack filtering and `subproject_path` assignment

**Files:**
- Modify: `radar-audit/src/radar_audit/orchestrator.py:107-155`
- Test: `radar-audit/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `ToolRunner.supported_stacks`, `ToolRunner.scope`, `ToolResult.subproject_path` (Tasks 1-2).
- Produces: `execute_audit` now sets `subproject_path` on every `ToolResult` it creates; runners with `scope == "repo"` run exactly once per audit; runners with `scope == "subproject"` skip sub-projects whose stack isn't in `supported_stacks`.

- [ ] **Step 1: Write the failing tests**

In `radar-audit/tests/test_orchestrator.py`, update `_StubRunner` and `_AlwaysCrashesRunner` to declare the new protocol attributes (needed for every existing test in this file to keep passing once Step 3 lands), and add three new tests:

```python
class _StubRunner:
    tool_name = "stub-runner"
    tool_version = "0.0.1"
    supported_stacks: frozenset[str] = frozenset({"unknown", "python", "javascript", "php"})
    scope = "subproject"
    timeout_s = 10

    def run(self, target_path, exclude_paths):
        return RawToolOutput(
            command="stub",
            raw_output={"ok": True},
            exit_code=0,
            duration_ms=1,
        )


class _AlwaysCrashesRunner:
    tool_name = "crashes-runner"
    tool_version = "0.0.1"
    supported_stacks: frozenset[str] = frozenset({"unknown", "python", "javascript", "php"})
    scope = "subproject"
    timeout_s = 10

    def run(self, target_path, exclude_paths):
        raise RuntimeError("boom")


class _RepoScopeStubRunner:
    tool_name = "repo-scope-stub"
    tool_version = "0.0.1"
    supported_stacks: frozenset[str] = frozenset()
    scope = "repo"
    timeout_s = 10

    def run(self, target_path, exclude_paths):
        return RawToolOutput(command="stub", raw_output={"ok": True}, exit_code=0, duration_ms=1)


class _JsOnlyStubRunner:
    tool_name = "js-only-stub"
    tool_version = "0.0.1"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope = "subproject"
    timeout_s = 10

    def run(self, target_path, exclude_paths):
        return RawToolOutput(command="stub", raw_output={"ok": True}, exit_code=0, duration_ms=1)


def test_execute_audit_sets_subproject_path_relative_to_repo_root(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"backend/pyproject.toml": "[project]\nname='x'\n", "frontend/package.json": "{}\n"},
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_StubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert {r.subproject_path for r in results} == {"backend", "frontend"}


def test_execute_audit_runs_repo_scope_runner_once_regardless_of_subproject_count(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"backend/pyproject.toml": "[project]\nname='x'\n", "frontend/package.json": "{}\n"},
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_RepoScopeStubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert len(results) == 1
    assert results[0].subproject_path == "."


def test_execute_audit_skips_runner_for_unsupported_stack(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname='x'\n"})
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_JsOnlyStubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — `test_execute_audit_sets_subproject_path_relative_to_repo_root` and the two new tests fail (`TypeError: 'subproject_path' is an invalid keyword argument` from `execute_audit`'s current `ToolResult(...)` call, and the skip/dedup tests fail their assertions since current code has no scope/stack filtering).

- [ ] **Step 3: Implement the orchestrator changes**

Replace `execute_audit` and `_run_tool_safely` in `radar-audit/src/radar_audit/orchestrator.py` (lines 107-155):

```python
def execute_audit(
    session: Session,
    config: PortfolioConfig,
    repo_name: str,
    runners: list[ToolRunner],
) -> Audit:
    plan = plan_audit(config, repo_name)

    seed_taxonomy(session)
    repository = resolve_repository(session, plan.repository_path, repo_name)
    audit = get_or_create_audit(session, repository)

    existing_results = session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    for result in existing_results:
        session.delete(result)

    repo_scope_done: set[str] = set()
    for subproject in plan.subprojects:
        for runner in runners:
            if runner.scope == "repo":
                if runner.tool_name in repo_scope_done:
                    continue
                repo_scope_done.add(runner.tool_name)
                target_path = plan.repository_path
            else:
                if subproject.stack not in runner.supported_stacks:
                    continue
                target_path = subproject.path

            raw = _run_tool_safely(runner, target_path, plan.exclude_paths)
            session.add(
                ToolResult(
                    audit_id=audit.id,
                    subproject_path=_relative_subproject_path(target_path, plan.repository_path),
                    tool_name=runner.tool_name,
                    tool_version=runner.tool_version,
                    command=raw.command,
                    raw_output=raw.raw_output,
                    exit_code=raw.exit_code,
                    duration_ms=raw.duration_ms,
                )
            )

    session.commit()
    session.refresh(audit)
    return audit


def _relative_subproject_path(target_path: Path, repository_path: Path) -> str:
    resolved_target = target_path.resolve()
    resolved_repo = repository_path.resolve()
    if resolved_target == resolved_repo:
        return "."
    return str(resolved_target.relative_to(resolved_repo))


def _run_tool_safely(
    runner: ToolRunner, target_path: Path, exclude_paths: list[Path]
) -> RawToolOutput:
    try:
        return runner.run(target_path, exclude_paths)
    except Exception as exc:  # noqa: BLE001 - a tool crash must persist as evidence, never abort the audit
        return RawToolOutput(
            command=f"{runner.tool_name} (crashed)",
            raw_output={"error": str(exc)},
            exit_code=-1,
            duration_ms=0,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/orchestrator.py radar-audit/tests/test_orchestrator.py
git commit -m "feat(radar-audit): filter runners by scope/stack, persist subproject_path"
```

---

### Task 4: `DesignDocRunner` (criterion 1.2)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/design_doc_runner.py`
- Test: `radar-audit/tests/test_design_doc_runner.py`

**Interfaces:**
- Consumes: `ToolRunner` protocol (Task 2), `RawToolOutput` (existing).
- Produces: `DesignDocRunner` (`tool_name="design-doc-presence"`, `scope="repo"`, `supported_stacks=frozenset()`), `raw_output` shape `{"found_path": str | None, "non_blank_lines": int}` — Task 11's normalizer reads exactly these two keys.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_design_doc_runner.py`:

```python
from radar_audit.runners.design_doc_runner import DesignDocRunner

from tests.git_helpers import init_git_repo


def test_reports_absent_when_no_doc_or_adr_dir_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["found_path"] is None
    assert result.raw_output["non_blank_lines"] == 0


def test_finds_design_md_at_repo_root(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"})

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "DESIGN.md")
    assert result.raw_output["non_blank_lines"] == 40


def test_finds_architecture_md_in_docs_directory(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"docs/ARCHITECTURE.md": "line one\nline two\n"})

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "docs" / "ARCHITECTURE.md")
    assert result.raw_output["non_blank_lines"] == 2


def test_sums_lines_across_adr_directory_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "docs/adr/0001-use-sqlite.md": "line one\nline two\n",
            "docs/adr/0002-use-typer.md": "line one\n",
        },
    )

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "docs" / "adr")
    assert result.raw_output["non_blank_lines"] == 3


def test_root_design_md_takes_priority_over_adr_directory(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "DESIGN.md": "line one\n",
            "docs/adr/0001-use-sqlite.md": "line one\nline two\nline three\n",
        },
    )

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "DESIGN.md")
    assert result.raw_output["non_blank_lines"] == 1


def test_reports_tool_identity():
    runner = DesignDocRunner()

    assert runner.tool_name == "design-doc-presence"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_design_doc_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.design_doc_runner'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/runners/design_doc_runner.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_DOC_FILENAMES = ("DESIGN.MD", "ARCHITECTURE.MD")
_ADR_DIRNAMES = ("adr", "decisions")


class DesignDocRunner:
    """Checks for DESIGN.md/ARCHITECTURE.md/ADR presence (criterion 1.2). No subprocess."""

    tool_name = "design-doc-presence"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        found_path, non_blank_lines = self._find_doc(target_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"filesystem-check {target_path}",
            raw_output={
                "found_path": str(found_path) if found_path is not None else None,
                "non_blank_lines": non_blank_lines,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _find_doc(self, target_path: Path) -> tuple[Path | None, int]:
        for directory in (target_path, target_path / "docs"):
            doc_path = self._find_named_file(directory)
            if doc_path is not None:
                return doc_path, self._count_non_blank_lines(doc_path)

        for adr_dirname in _ADR_DIRNAMES:
            adr_dir = target_path / "docs" / adr_dirname
            if adr_dir.is_dir():
                md_files = sorted(adr_dir.glob("*.md"))
                if md_files:
                    total_lines = sum(self._count_non_blank_lines(f) for f in md_files)
                    return adr_dir, total_lines

        return None, 0

    def _find_named_file(self, directory: Path) -> Path | None:
        if not directory.is_dir():
            return None
        for entry in directory.iterdir():
            if entry.is_file() and entry.name.upper() in _DOC_FILENAMES:
                return entry
        return None

    def _count_non_blank_lines(self, file_path: Path) -> int:
        return sum(1 for line in file_path.read_text().splitlines() if line.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_design_doc_runner.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/design_doc_runner.py radar-audit/tests/test_design_doc_runner.py
git commit -m "feat(radar-audit): add DesignDocRunner for criterion 1.2"
```

---

### Task 5: `StaticLocRunner` (criterion 1.3, JS/PHP)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/static_loc_runner.py`
- Test: `radar-audit/tests/test_static_loc_runner.py`

**Interfaces:**
- Consumes: `ToolRunner` protocol (Task 2).
- Produces: `StaticLocRunner` (`tool_name="static-loc-count"`, `scope="subproject"`, `supported_stacks={"javascript", "php"}`), `raw_output` shape `{"files": {"<absolute path>": <non_blank_line_count>}}` — Task 12's normalizer reads the `"files"` key.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_static_loc_runner.py`:

```python
from radar_audit.runners.static_loc_runner import StaticLocRunner

from tests.git_helpers import init_git_repo


def test_counts_non_blank_lines_per_source_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "line one\n\nline three\n",
            "src/b.php": "<?php\necho 1;\n",
            "README.md": "not counted\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    files = result.raw_output["files"]
    assert files[str(repo_path / "src" / "a.js")] == 2
    assert files[str(repo_path / "src" / "b.php")] == 2
    assert str(repo_path / "README.md") not in files
    assert result.exit_code == 0


def test_skips_vendor_and_node_modules_directories(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "line\n",
            "node_modules/pkg/index.js": "line\n",
            "vendor/lib/file.php": "<?php\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    files = result.raw_output["files"]
    assert set(files) == {str(repo_path / "src" / "a.js")}


def test_reports_tool_identity():
    runner = StaticLocRunner()

    assert runner.tool_name == "static-loc-count"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript", "php"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_static_loc_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.static_loc_runner'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/runners/static_loc_runner.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SOURCE_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".vue", ".php"}
_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class StaticLocRunner:
    """Counts non-blank lines per JS/TS/Vue/PHP source file via a plain filesystem walk
    (criterion 1.3 — no dedicated LOC tool validated for these stacks, see toolchain.md).
    """

    tool_name = "static-loc-count"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript", "php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        per_file: dict[str, int] = {}
        for file_path in sorted(target_path.rglob("*")):
            if not file_path.is_file() or file_path.suffix not in _SOURCE_EXTENSIONS:
                continue
            if self._is_skipped(file_path, exclude_paths):
                continue
            per_file[str(file_path)] = self._count_non_blank_lines(file_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"static-loc-walk {target_path}",
            raw_output={"files": per_file},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _is_skipped(self, file_path: Path, exclude_paths: list[Path]) -> bool:
        if any(part in _SKIP_DIRNAMES for part in file_path.parts):
            return True
        return any(
            excluded == file_path or excluded in file_path.parents for excluded in exclude_paths
        )

    def _count_non_blank_lines(self, file_path: Path) -> int:
        return sum(1 for line in file_path.read_text(errors="ignore").splitlines() if line.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_static_loc_runner.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/static_loc_runner.py radar-audit/tests/test_static_loc_runner.py
git commit -m "feat(radar-audit): add StaticLocRunner for criterion 1.3"
```

---

### Task 6: `RadonModuleSizeRunner` (criterion 1.3, Python)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/radon_module_size_runner.py`
- Test: `radar-audit/tests/test_radon_module_size_runner.py`

**Interfaces:**
- Consumes: `ToolRunner` protocol (Task 2).
- Produces: `RadonModuleSizeRunner` (`tool_name="radon-raw"`, `scope="subproject"`, `supported_stacks={"python"}`), `raw_output` shape `{"<file path>": {"loc": int, "sloc": int, ...}, ...}` (radon's native `raw --json` schema) — Task 12's normalizer reads each entry's `"sloc"` key.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_radon_module_size_runner.py`:

```python
from radar_audit.runners.radon_module_size_runner import RadonModuleSizeRunner

from tests.git_helpers import init_git_repo


def test_reports_sloc_per_python_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pkg/__init__.py": "",
            "pkg/mod.py": "x = 1\ny = 2\n\n# comment\n",
        },
    )

    runner = RadonModuleSizeRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    mod_key = str(repo_path / "pkg" / "mod.py")
    assert mod_key in result.raw_output
    assert result.raw_output[mod_key]["sloc"] == 2


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pkg/mod.py": "x = 1\n",
            "vendored/dep.py": "y = 2\n",
        },
    )

    runner = RadonModuleSizeRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "vendored"])

    assert str(repo_path / "pkg" / "mod.py") in result.raw_output
    assert str(repo_path / "vendored" / "dep.py") not in result.raw_output


def test_reports_tool_identity():
    runner = RadonModuleSizeRunner()

    assert runner.tool_name == "radon-raw"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_radon_module_size_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.radon_module_size_runner'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/runners/radon_module_size_runner.py`:

```python
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_GLOB_SUFFIXES = ("/.venv/*", "/__pycache__/*", "/node_modules/*", "/vendor/*", "/dist/*", "/build/*")


class RadonModuleSizeRunner:
    """Reports per-file LOC for Python modules via radon (criterion 1.3)."""

    tool_name = "radon-raw"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        patterns = [f"{target_path}{suffix}" for suffix in _SKIP_GLOB_SUFFIXES]
        patterns.extend(f"{excluded}/*" for excluded in exclude_paths)

        command = ["uvx", "radon", "raw", "--json", "-e", ",".join(patterns), str(target_path)]

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

Note: the `-e` exclude glob patterns are built as **absolute** paths (`f"{target_path}{suffix}"` / `f"{excluded}/*"`) because radon's own exclude matching operates on whatever path form (absolute, since the orchestrator always passes a resolved `target_path`) it was invoked with — confirmed empirically; a relative glob does not match when `radon` is given an absolute target path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_radon_module_size_runner.py -v`
Expected: PASS (all 3 tests). Note: this test's first run in a fresh environment needs network access to fetch `radon` into the `uv` tool cache (D7 — not a new risk, see spec §8).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/radon_module_size_runner.py \
        radar-audit/tests/test_radon_module_size_runner.py
git commit -m "feat(radar-audit): add RadonModuleSizeRunner for criterion 1.3"
```

---

### Task 7: `DependencyCruiserRunner` (criterion 1.1, JS)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py`
- Test: `radar-audit/tests/test_dependency_cruiser_runner.py`

**Interfaces:**
- Consumes: `ToolRunner` protocol (Task 2).
- Produces: `DependencyCruiserRunner` (`tool_name="dependency-cruiser"`, `scope="subproject"`, `supported_stacks={"javascript"}`), `raw_output` shape `{"modules": [{"source": str, "dependencies": [{"resolved": str, "circular": bool, ...}], ...}], ...}` (dependency-cruiser's native JSON schema) — Task 10's normalizer reads `modules[].source` and `modules[].dependencies[].circular`/`.resolved`.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_dependency_cruiser_runner.py`:

```python
from radar_audit.runners.dependency_cruiser_runner import DependencyCruiserRunner

from tests.git_helpers import init_git_repo


def test_reports_no_circular_dependencies_on_a_clean_tree(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export const a = 1;\n",
            "src/b.js": "import { a } from './a.js';\nexport const b = a + 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    circular_deps = [d for m in modules for d in m["dependencies"] if d["circular"]]
    assert circular_deps == []


def test_detects_a_circular_import(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "import { b } from './b.js';\nexport const a = 1;\n",
            "src/b.js": "import { a } from './a.js';\nexport const b = 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    circular_deps = [d for m in modules for d in m["dependencies"] if d["circular"]]
    assert len(circular_deps) == 2  # a->b and b->a each flagged


def test_reports_tool_identity():
    runner = DependencyCruiserRunner()

    assert runner.tool_name == "dependency-cruiser"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_dependency_cruiser_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.dependency_cruiser_runner'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py`:

```python
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class DependencyCruiserRunner:
    """Detects circular JS/TS dependencies via dependency-cruiser (criterion 1.1)."""

    tool_name = "dependency-cruiser"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = [
            "npx",
            "--package=dependency-cruiser",
            "--",
            "depcruise",
            "--no-config",
            "--output-type",
            "json",
        ]
        exclude_pattern = self._build_exclude_pattern(target_path, exclude_paths)
        if exclude_pattern is not None:
            command.extend(["-x", exclude_pattern])
        command.append(str(target_path))

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _build_exclude_pattern(self, target_path: Path, exclude_paths: list[Path]) -> str | None:
        relative_patterns = []
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue  # not under target_path, dependency-cruiser will never visit it
            relative_patterns.append(re.escape(relative.as_posix()))
        return "|".join(relative_patterns) if relative_patterns else None
```

Note: dependency-cruiser reports module `source`/`resolved` paths **relative to the cruised directory**, regardless of whether `target_path` was given as an absolute or relative path — confirmed empirically. `-x` therefore needs a pattern built relative to `target_path`, not an absolute-path regex (which never matches).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_dependency_cruiser_runner.py -v`
Expected: PASS (all 3 tests). First run in a fresh environment needs network access to fetch `dependency-cruiser` into the `npx` cache (D7).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py \
        radar-audit/tests/test_dependency_cruiser_runner.py
git commit -m "feat(radar-audit): add DependencyCruiserRunner for criterion 1.1"
```

---

### Task 8: `PydepsRunner` (criterion 1.1, Python)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/pydeps_runner.py`
- Test: `radar-audit/tests/test_pydeps_runner.py`

**Interfaces:**
- Consumes: `ToolRunner` protocol (Task 2).
- Produces: `PydepsRunner` (`tool_name="pydeps"`, `scope="subproject"`, `supported_stacks={"python"}`), `raw_output` shape `{"module.name": {"imports": [str, ...] (may be absent), "imported_by": [str, ...], "bacon": int, "name": str, "path": str | None}, ...}` — Task 10's normalizer reads every entry's `"imports"` key (defaulting to `[]` if absent).

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_pydeps_runner.py`:

```python
from radar_audit.runners.pydeps_runner import PydepsRunner

from tests.git_helpers import init_git_repo


def test_reports_no_cycle_on_a_clean_package(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
        },
    )

    runner = PydepsRunner()
    result = runner.run(repo_path / "mypkg", exclude_paths=[])

    assert result.exit_code == 0
    assert "mypkg.a" in result.raw_output
    assert result.raw_output["mypkg.a"]["imports"] == ["mypkg", "mypkg.b"]
    assert "imports" not in result.raw_output["mypkg.b"]


def test_reports_a_circular_import_between_two_modules(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "from mypkg import a\n",
        },
    )

    runner = PydepsRunner()
    result = runner.run(repo_path / "mypkg", exclude_paths=[])

    assert result.exit_code == 0
    assert set(result.raw_output["mypkg.a"]["imports"]) == {"mypkg", "mypkg.b"}
    assert set(result.raw_output["mypkg.b"]["imports"]) == {"mypkg", "mypkg.a"}


def test_reports_tool_identity():
    runner = PydepsRunner()

    assert runner.tool_name == "pydeps"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pydeps_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pydeps_runner'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/runners/pydeps_runner.py`:

```python
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PydepsRunner:
    """Reports the Python import graph via pydeps, used for cycle detection (criterion 1.1).

    Uses `--show-deps --no-output --max-bacon=0` rather than `--show-cycles`: live testing
    showed `--show-cycles` produces no usable stdout even against a genuine cycle, while
    `--show-deps` reliably returns a structured JSON import graph. Cycle detection itself
    runs in the normalizer (a DFS over each module's `imports` adjacency list), not here.

    Accuracy depends on `target_path` being an actual importable package root (contains
    `__init__.py`, its directory name matching the import style used inside it) — see the
    plan's "Known limitation" note.
    """

    tool_name = "pydeps"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["uvx", "pydeps", str(target_path), "--show-deps", "--no-output", "--max-bacon=0"]

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
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

Run: `cd radar-audit && uv run pytest tests/test_pydeps_runner.py -v`
Expected: PASS (all 3 tests). First run in a fresh environment needs network access to fetch `pydeps` into the `uv` tool cache (D7).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pydeps_runner.py radar-audit/tests/test_pydeps_runner.py
git commit -m "feat(radar-audit): add PydepsRunner for criterion 1.1"
```

---

### Task 9: Normalizer shared helpers

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/__init__.py` (empty)
- Create: `radar-audit/src/radar_audit/normalizers/shared.py`
- Test: `radar-audit/tests/test_normalizers_shared.py`

**Interfaces:**
- Consumes: `radar_core.models.audit.Audit`, `radar_core.models.methodology.{Category, Criterion, MethodologyVersion}`, `radar_core.models.scoring.ScoringRun`, `radar_audit.taxonomy.seed.seed_taxonomy` (all existing).
- Produces: `get_or_create_scoring_run(session, audit, methodology_version) -> ScoringRun`, `get_criterion(session, methodology_version_id, category_name, criterion_name) -> Criterion`, `CriterionNotFoundError(ValueError)` — Tasks 10-12 call both functions.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/src/radar_audit/normalizers/__init__.py` (empty file).

Create `radar-audit/tests/test_normalizers_shared.py`:

```python
import pytest
from radar_audit.normalizers.shared import CriterionNotFoundError, get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository


def _make_audit(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_get_or_create_scoring_run_creates_a_new_run(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert scoring_run.id is not None
    assert scoring_run.audit_id == audit.id
    assert scoring_run.methodology_version_id == methodology_version.id


def test_get_or_create_scoring_run_reuses_existing(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    first = get_or_create_scoring_run(db_session, audit, methodology_version)
    second = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert first.id == second.id


def test_get_criterion_finds_a_seeded_criterion(db_session):
    methodology_version = seed_taxonomy(db_session)

    criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Dependency direction / circularity",
    )

    assert criterion.name == "Dependency direction / circularity"


def test_get_criterion_raises_when_not_found(db_session):
    methodology_version = seed_taxonomy(db_session)

    with pytest.raises(CriterionNotFoundError):
        get_criterion(db_session, methodology_version.id, "Nonexistent", "Nope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalizers_shared.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.shared'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/normalizers/shared.py`:

```python
from __future__ import annotations

from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select


def get_or_create_scoring_run(
    session: Session, audit: Audit, methodology_version: MethodologyVersion
) -> ScoringRun:
    """Get or create the ScoringRun for this Audit + MethodologyVersion pair.

    Mirrors orchestrator.get_or_create_audit's reuse pattern, keyed on the model's
    (audit_id, methodology_version_id) unique constraint.
    """
    existing = session.exec(
        select(ScoringRun).where(
            ScoringRun.audit_id == audit.id,
            ScoringRun.methodology_version_id == methodology_version.id,
        )
    ).first()
    if existing is not None:
        return existing

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    session.add(scoring_run)
    session.commit()
    session.refresh(scoring_run)
    return scoring_run


class CriterionNotFoundError(ValueError):
    """Raised when a (category_name, criterion_name) pair isn't found in the seeded taxonomy."""


def get_criterion(
    session: Session,
    methodology_version_id: int,
    category_name: str,
    criterion_name: str,
) -> Criterion:
    """Look up a seeded Criterion by its category and criterion name, exactly as seeded from
    quality_framework_v1_0.yaml.
    """
    criterion = session.exec(
        select(Criterion)
        .join(Category, Category.id == Criterion.category_id)  # type: ignore[arg-type]
        .where(
            Category.methodology_version_id == methodology_version_id,
            Category.name == category_name,
            Criterion.name == criterion_name,
        )
    ).first()
    if criterion is None:
        raise CriterionNotFoundError(
            f"No criterion {criterion_name!r} in category {category_name!r} "
            f"for methodology_version_id={methodology_version_id}"
        )
    return criterion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalizers_shared.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/src/radar_audit/normalizers/shared.py \
        radar-audit/tests/test_normalizers_shared.py
git commit -m "feat(radar-audit): add scoring-run/criterion lookup helpers for normalizers"
```

---

### Task 10: Normalize criterion 1.1 (dependency circularity)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/dependency_circularity.py`
- Test: `radar-audit/tests/test_normalize_dependency_circularity.py`

**Interfaces:**
- Consumes: `get_or_create_scoring_run`, `get_criterion`, `CriterionNotFoundError` (Task 9); `DependencyCruiserRunner`/`PydepsRunner`'s `raw_output` shapes (Tasks 7-8); `radar_core.models.{finding.Finding, scoring.Score, audit.ToolResult, methodology.Criterion, scoring.ScoringRun}`; `radar_core.enums.{Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel}`.
- Produces: `normalize_dependency_circularity(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_normalize_dependency_circularity.py`:

```python
from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        "Architecture & design",
        "Dependency direction / circularity",
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, tool_name, raw_output, subproject_path="."):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=subproject_path,
        tool_name=tool_name,
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_cycles_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {"modules": [{"source": "a.js", "dependencies": []}]},
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.level == ScoreLevel.CRITERION
    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_one_dependency_cruiser_cycle_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {
            "modules": [
                {
                    "source": "a.js",
                    "dependencies": [{"resolved": "b.js", "circular": True}],
                },
                {
                    "source": "b.js",
                    "dependencies": [{"resolved": "a.js", "circular": True}],
                },
            ]
        },
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].tool_result_id == tool_result.id


def test_pydeps_cycle_is_detected_via_dfs(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pydeps",
        {
            "mypkg": {"imported_by": ["mypkg.a", "mypkg.b"]},
            "mypkg.a": {"imports": ["mypkg", "mypkg.b"], "imported_by": ["mypkg.b"]},
            "mypkg.b": {"imports": ["mypkg", "mypkg.a"], "imported_by": ["mypkg.a"]},
        },
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_worst_band_wins_across_two_subprojects(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    clean = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {"modules": [{"source": "a.js", "dependencies": []}]},
        subproject_path="frontend",
    )
    broken = _make_tool_result(
        db_session,
        audit,
        "pydeps",
        {
            "mypkg": {"imported_by": ["mypkg.a", "mypkg.b", "mypkg.c"]},
            "mypkg.a": {"imports": ["mypkg.b"], "imported_by": []},
            "mypkg.b": {"imports": ["mypkg.c"], "imported_by": ["mypkg.a"]},
            "mypkg.c": {"imports": ["mypkg.a"], "imported_by": ["mypkg.b"]},
        },
        subproject_path="backend",
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [clean, broken])

    # broken has exactly one 3-node cycle (a->b->c->a) -> band 4 (3-5 cycles); worst wins over clean's 10
    assert score.value == 4.0


def test_skips_failed_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    failed = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="pydeps",
        tool_version="1.0.0",
        command="stub",
        raw_output={"error": "crashed"},
        exit_code=-1,
        duration_ms=0,
    )
    db_session.add(failed)
    db_session.commit()
    db_session.refresh(failed)

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [failed])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    unrelated = _make_tool_result(db_session, audit, "design-doc-presence", {"found_path": None})

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [unrelated])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dependency_circularity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.dependency_circularity'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/normalizers/dependency_circularity.py`:

```python
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"dependency-cruiser", "pydeps"}
# Band thresholds per quality-framework.md§4.1: 0=10, 1-2=6, 3-5=4, >5=2.
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (2, 6.0), (5, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_dependency_circularity(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name in _RELEVANT_TOOLS and r.exit_code == 0]
    if not relevant:
        return None

    worst_value: float | None = None
    for tool_result in relevant:
        cycles = _detect_cycles(tool_result)
        for cycle_nodes in cycles:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.MEDIUM,
                    description=f"Circular dependency involving: {', '.join(sorted(cycle_nodes))}",
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
        value = _band_value(len(cycles))
        if worst_value is None or value < worst_value:
            worst_value = value

    assert worst_value is not None  # relevant is non-empty, so the loop above always ran

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=worst_value,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(cycle_count: int) -> float:
    for max_count, value in _BANDS:
        if cycle_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _detect_cycles(tool_result: ToolResult) -> list[frozenset[str]]:
    if tool_result.tool_name == "dependency-cruiser":
        return _detect_cycles_dependency_cruiser(tool_result.raw_output)
    return _detect_cycles_pydeps(tool_result.raw_output)


def _detect_cycles_dependency_cruiser(raw_output: dict[str, object]) -> list[frozenset[str]]:
    modules = raw_output.get("modules", [])
    cycles: list[frozenset[str]] = []
    for module in modules:  # type: ignore[union-attr]
        source = module["source"]
        for dependency in module.get("dependencies", []):
            if dependency.get("circular"):
                cycles.append(frozenset({source, dependency["resolved"]}))
    return cycles


def _detect_cycles_pydeps(raw_output: dict[str, object]) -> list[frozenset[str]]:
    adjacency = {
        name: data.get("imports", []) for name, data in raw_output.items() if isinstance(data, dict)
    }
    visited: set[str] = set()
    in_stack: set[str] = set()
    found: set[frozenset[str]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in in_stack:
            cycle_start = path.index(node)
            found.add(frozenset(path[cycle_start:]))
            return
        if node in visited or node not in adjacency:
            return
        visited.add(node)
        in_stack.add(node)
        for neighbor in adjacency.get(node, []):
            visit(neighbor, path + [node])
        in_stack.discard(node)

    for module_name in adjacency:
        if module_name not in visited:
            visit(module_name, [])

    return list(found)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dependency_circularity.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/dependency_circularity.py \
        radar-audit/tests/test_normalize_dependency_circularity.py
git commit -m "feat(radar-audit): normalize criterion 1.1 dependency circularity"
```

---

### Task 11: Normalize criterion 1.2 (architectural documentation)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/design_doc.py`
- Test: `radar-audit/tests/test_normalize_design_doc.py`

**Interfaces:**
- Consumes: `get_or_create_scoring_run`, `get_criterion` (Task 9); `DesignDocRunner`'s `raw_output` shape (Task 4).
- Produces: `normalize_design_doc(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_normalize_design_doc.py`:

```python
from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        db_session, methodology_version.id, "Architecture & design", "Architectural documentation present"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="design-doc-presence",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_absent_scores_zero_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"found_path": None, "non_blank_lines": 0})

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 0.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].severity == "LOW"


def test_present_and_trivial_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"found_path": "/repo/DESIGN.md", "non_blank_lines": 5}
    )

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_present_and_non_trivial_scores_ten_with_no_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"found_path": "/repo/DESIGN.md", "non_blank_lines": 40}
    )

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_returns_none_when_no_relevant_tool_results(db_session):
    _, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_design_doc(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_design_doc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.design_doc'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/normalizers/design_doc.py`:

```python
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Provisional threshold, not yet calibrated against the real portfolio (see spec §7/§9).
_NON_TRIVIAL_LINE_THRESHOLD = 30


def normalize_design_doc(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.tool_name == "design-doc-presence" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    found_path = tool_result.raw_output.get("found_path")
    non_blank_lines = tool_result.raw_output.get("non_blank_lines", 0)

    if found_path is None:
        value = 0.0
        _add_finding(session, scoring_run, criterion, tool_result, "no architectural documentation found")
    elif non_blank_lines >= _NON_TRIVIAL_LINE_THRESHOLD:
        value = 10.0
    else:
        value = 6.0
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            f"architectural documentation at {found_path} is trivial ({non_blank_lines} non-blank lines)",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    description: str,
) -> None:
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_design_doc.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/design_doc.py radar-audit/tests/test_normalize_design_doc.py
git commit -m "feat(radar-audit): normalize criterion 1.2 architectural documentation"
```

---

### Task 12: Normalize criterion 1.3 (module size distribution)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/module_size.py`
- Test: `radar-audit/tests/test_normalize_module_size.py`

**Interfaces:**
- Consumes: `get_or_create_scoring_run`, `get_criterion` (Task 9); `RadonModuleSizeRunner`'s and `StaticLocRunner`'s `raw_output` shapes (Tasks 5-6).
- Produces: `normalize_module_size(session, scoring_run, criterion, tool_results) -> Score | None`.

- [ ] **Step 1: Write the failing tests**

Create `radar-audit/tests/test_normalize_module_size.py`:

```python
from radar_audit.normalizers.module_size import normalize_module_size
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        db_session, methodology_version.id, "Architecture & design", "Module size distribution"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, tool_name, raw_output, subproject_path="."):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=subproject_path,
        tool_name=tool_name,
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_all_modules_covered_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}, "b.py": {"sloc": 200}}
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_one_oversized_module_creates_a_finding_and_lowers_score(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}, "big.py": {"sloc": 500}}
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 5.0  # 1 covered / 2 applicable * 10
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "big.py"


def test_covered_and_applicable_are_summed_across_two_subprojects(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    radon_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}}, subproject_path="backend"
    )
    static_result = _make_tool_result(
        db_session,
        audit,
        "static-loc-count",
        {"files": {"a.js": 100, "b.js": 500}},
        subproject_path="frontend",
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [radon_result, static_result])

    assert score.value == pytest_approx(20.0 / 3)


def pytest_approx(value):
    import pytest

    return pytest.approx(value)


def test_zero_applicable_modules_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, "static-loc-count", {"files": {}})

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score is None
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_returns_none_when_no_relevant_tool_results(db_session):
    _, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_module_size(db_session, scoring_run, criterion, [])

    assert score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_normalize_module_size.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.module_size'`.

- [ ] **Step 3: Write the implementation**

Create `radar-audit/src/radar_audit/normalizers/module_size.py`:

```python
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"radon-raw", "static-loc-count"}
# Provisional threshold, not yet calibrated against the real portfolio (see spec §7/§9).
_COVERED_LOC_THRESHOLD = 400


def normalize_module_size(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name in _RELEVANT_TOOLS and r.exit_code == 0]
    if not relevant:
        return None

    covered = 0
    applicable = 0
    for tool_result in relevant:
        for file_path, loc in _per_file_loc(tool_result).items():
            applicable += 1
            if loc <= _COVERED_LOC_THRESHOLD:
                covered += 1
            else:
                session.add(
                    Finding(
                        scoring_run_id=scoring_run.id,
                        criterion_id=criterion.id,
                        tool_result_id=tool_result.id,
                        severity=FindingSeverity.LOW,
                        description=(
                            f"{file_path} is {loc} non-blank lines, over the "
                            f"{_COVERED_LOC_THRESHOLD}-line threshold"
                        ),
                        file=file_path,
                        confidence=Confidence.MEDIUM,
                        status=FindingStatus.OPEN,
                        human_verdict=HumanVerdict.UNREVIEWED,
                    )
                )

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


def _per_file_loc(tool_result: ToolResult) -> dict[str, int]:
    if tool_result.tool_name == "radon-raw":
        return {path: data["sloc"] for path, data in tool_result.raw_output.items()}
    return dict(tool_result.raw_output.get("files", {}))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest tests/test_normalize_module_size.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/module_size.py radar-audit/tests/test_normalize_module_size.py
git commit -m "feat(radar-audit): normalize criterion 1.3 module size distribution"
```

---

### Task 13: Wire the real runners into the CLI, remove the example runner, end-to-end test

**Files:**
- Modify: `radar-audit/src/radar_audit/cli.py:1-18`
- Modify: `radar-audit/tests/test_cli.py:18-28,70-99`
- Delete: `radar-audit/src/radar_audit/runners/example.py`
- Delete: `radar-audit/tests/test_runner.py`
- Test: `radar-audit/tests/test_category_1_end_to_end.py`

**Interfaces:**
- Consumes: all five runners (Tasks 4-8), all three normalizers (Tasks 10-12), `get_or_create_scoring_run`/`get_criterion` (Task 9), `execute_audit` (Task 3).
- Produces: `radar_audit.cli.DEFAULT_RUNNERS` now lists the five real runners; nothing later in this plan depends on this task's output (it's the terminal task).

- [ ] **Step 1: Write the failing tests**

Modify `radar-audit/tests/test_cli.py`'s `test_dry_run_prints_plan_and_writes_nothing_to_disk` (lines 18-28):

```python
def test_dry_run_prints_plan_and_writes_nothing_to_disk(tmp_path):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "sample-repo" in result.stdout
    assert "dependency-cruiser" in result.stdout
    assert "pydeps" in result.stdout
    assert "design-doc-presence" in result.stdout
    assert "radon-raw" in result.stdout
    assert "static-loc-count" in result.stdout
    assert not (tmp_path / "radar.db").exists()
```

Modify `radar-audit/tests/test_cli.py`'s `test_real_run_persists_audit_and_tool_results` (lines 70-99), changing only the final assertion:

```python
    assert result.exit_code == 0
    assert db_path.exists()

    from radar_core.db import get_engine
    from radar_core.models.audit import Audit, ToolResult

    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        audits = session.exec(select(Audit)).all()
        assert len(audits) == 1
        results = session.exec(select(ToolResult)).all()
        # repo fixture has no manifest -> stack="unknown" -> only the repo-scoped
        # DesignDocRunner (stack-independent) runs; the other four are subproject-scoped
        # and skip an "unknown" stack.
        assert len(results) == 1
        assert results[0].tool_name == "design-doc-presence"
```

Delete `radar-audit/tests/test_runner.py` (its only subject, `ExampleGitLogRunner`, is being removed).

Create `radar-audit/tests/test_category_1_end_to_end.py`:

```python
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.module_size import normalize_module_size
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.orchestrator import execute_audit
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.scoring import Score
from sqlmodel import select

from tests.git_helpers import init_git_repo

from radar_audit.cli import DEFAULT_RUNNERS


def test_full_pipeline_from_audit_to_criterion_scores(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    tool_results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert {r.tool_name for r in tool_results} >= {"design-doc-presence", "pydeps", "radon-raw"}

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    circularity_criterion = get_criterion(
        db_session, methodology_version.id, "Architecture & design", "Dependency direction / circularity"
    )
    doc_criterion = get_criterion(
        db_session, methodology_version.id, "Architecture & design", "Architectural documentation present"
    )
    size_criterion = get_criterion(
        db_session, methodology_version.id, "Architecture & design", "Module size distribution"
    )

    normalize_dependency_circularity(db_session, scoring_run, circularity_criterion, tool_results)
    normalize_design_doc(db_session, scoring_run, doc_criterion, tool_results)
    normalize_module_size(db_session, scoring_run, size_criterion, tool_results)

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    assert len(scores) == 3
    assert all(s.level == ScoreLevel.CRITERION for s in scores)

    doc_score = next(s for s in scores if s.criterion_id == doc_criterion.id)
    assert doc_score.value == 10.0  # DESIGN.md has 40 non-blank lines, above the 30-line threshold
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_cli.py tests/test_category_1_end_to_end.py -v`
Expected: FAIL — `test_dry_run_...` and `test_real_run_...` fail their new assertions (CLI still uses `ExampleGitLogRunner`); `test_category_1_end_to_end.py` fails with `ImportError` since `DEFAULT_RUNNERS` still only contains the example runner and doesn't exercise the real ones.

- [ ] **Step 3: Wire the real runners and delete the example runner**

Replace the top of `radar-audit/src/radar_audit/cli.py` (lines 1-18):

```python
from __future__ import annotations

import os
from pathlib import Path
from subprocess import CalledProcessError

import typer
from radar_core.db import get_engine, get_session

from radar_audit.config import PortfolioConfigError, load_portfolio_config
from radar_audit.orchestrator import AuditPlan, execute_audit, plan_audit
from radar_audit.runner import ToolRunner
from radar_audit.runners.dependency_cruiser_runner import DependencyCruiserRunner
from radar_audit.runners.design_doc_runner import DesignDocRunner
from radar_audit.runners.pydeps_runner import PydepsRunner
from radar_audit.runners.radon_module_size_runner import RadonModuleSizeRunner
from radar_audit.runners.static_loc_runner import StaticLocRunner

app = typer.Typer()

DEFAULT_PORTFOLIO_YAML = Path(__file__).resolve().parents[2] / "portfolio.yaml"
DEFAULT_RUNNERS: list[ToolRunner] = [
    DependencyCruiserRunner(),
    PydepsRunner(),
    DesignDocRunner(),
    RadonModuleSizeRunner(),
    StaticLocRunner(),
]
```

The rest of `cli.py` (from `class MissingDatabaseUrlError` onward) is unchanged.

Delete `radar-audit/src/radar_audit/runners/example.py`.

Delete `radar-audit/tests/test_runner.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd radar-audit && uv run pytest -v`
Expected: PASS (the entire `radar-audit` test suite, including `test_cli.py` and `test_category_1_end_to_end.py`).

- [ ] **Step 5: Run the full workspace test suite and type checks**

Run: `cd radar-core && uv run pytest -v && uv run mypy src`
Run: `cd radar-audit && uv run pytest -v && uv run mypy src && uv run ruff check src tests`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add radar-audit/src/radar_audit/cli.py radar-audit/tests/test_cli.py \
        radar-audit/tests/test_category_1_end_to_end.py
git rm radar-audit/src/radar_audit/runners/example.py radar-audit/tests/test_runner.py
git commit -m "feat(radar-audit): wire category-1 runners into the CLI, remove example runner"
```

---
