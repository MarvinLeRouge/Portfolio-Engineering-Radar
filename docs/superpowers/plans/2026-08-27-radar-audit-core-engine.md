# radar-audit Core Engine (Increment 2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `radar-audit`'s core orchestration engine: discover repos/sub-projects, run a throwaway example `ToolRunner` end-to-end, persist `ToolResult`/`Audit` rows, and seed the full Quality Framework v1.0 taxonomy — with zero category-specific tool integration or normalization logic.

**Architecture:** A new uv workspace member (`radar-audit/`) depending on `radar-core` for models/db helpers. A Typer CLI (`radar-audit run`) drives a sequential orchestrator: load config → resolve `Repository` → seed taxonomy → create `Audit` → discover sub-projects → compute worktree exclusions → run registered `ToolRunner`s → persist `ToolResult` per run, continuing past individual tool failures.

**Tech Stack:** Python 3.12, uv, SQLModel (via `radar-core`), Typer, PyYAML, pytest, ruff, mypy (strict).

**Spec:** `docs/superpowers/specs/2026-08-27-radar-audit-core-engine-design.md`

## Global Constraints

- `radar-audit` is a new uv workspace member (root `pyproject.toml`), depending on `radar-core` via `[tool.uv.sources] radar-core = { workspace = true }`.
- Python 3.12, ruff + ruff-format + mypy (strict) — same toolchain discipline as `radar-core`; extend `.pre-commit-config.yaml` to cover `radar-audit/` alongside the existing `radar-core/` scope.
- CLI via Typer.
- `portfolio.yaml` (repo config) and `quality_framework_v1_0.yaml` (taxonomy) are YAML, versioned in git (not gitignored — only `radar.db` is, already covered by the repo's `*.db` gitignore rule).
- No environment-variable override for `repos_root` — `portfolio.yaml` is the single source of truth for it.
- `RADAR_DATABASE_URL` must be set explicitly for real CLI runs — no implicit default, consistent with `radar-core`'s existing `db.py`/`env.py` convention (production code must never silently fall back to `radar.db`).
- `ToolResult.raw_output` stays DB-only (existing JSON column on `radar_core.models.audit.ToolResult`) — no filesystem raw-output tree.
- Sequential tool execution; a single tool's failure (crash, timeout, non-zero exit) never aborts the whole audit — it is still persisted as a `ToolResult` recording the failure.
- Tests never depend on real external tools (only `git`, already a portfolio-wide prerequisite) or on `~/projets/`'s actual repos — fixtures are self-contained git repos created in `pytest`'s `tmp_path`.
- Running the real CLI against a fresh `radar.db` requires `radar-core`'s Alembic migrations to already be applied against the same `RADAR_DATABASE_URL` (`uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head`) — increment 2.0 does not automate this bootstrap step; it is an operational prerequisite, documented in `radar-audit/README.md` (Task 10).
- Existing `radar_core` model fields used verbatim (do not rename or reshape): `Repository(id, name, path, created_at)`, `Audit(id, repository_id, commit_sha, is_dirty, audited_at, network_flags)`, `ToolResult(id, audit_id, tool_name, tool_version, command, raw_output, exit_code, ran_at, duration_ms)`, `MethodologyVersion(id, version_label, frozen_at, notes)`, `Category(id, methodology_version_id, name, weight, order)`, `Criterion(id, category_id, name, description, weight, scoring_model)`, `radar_core.enums.ScoringModel` (`FIXED_SCALE`, `STATUS_4STATE`).
- `Audit` has a unique index on `(repository_id, commit_sha)` where `is_dirty = 0` (`radar_core/src/radar_core/models/audit.py:14-22`) — re-running an audit against the same clean commit must reuse the existing `Audit` row rather than attempt a duplicate insert (Task 8).

---

## File Structure

```
pyproject.toml                                    # MODIFY: add "radar-audit" to workspace members
.pre-commit-config.yaml                           # MODIFY: extend ruff/mypy hooks to radar-audit/
radar-audit/
├── pyproject.toml                                 # package metadata, deps, uv source, entry point
├── portfolio.yaml                                 # versioned config: repos_root + in-scope repos
├── README.md                                       # usage + migration-bootstrap note
├── src/radar_audit/
│   ├── __init__.py
│   ├── cli.py                                     # Typer app: `radar-audit run`
│   ├── config.py                                  # PortfolioConfig, load_portfolio_config
│   ├── discovery.py                               # SubProject, discover_subprojects
│   ├── worktree.py                                # compute_exclude_paths
│   ├── runner.py                                  # RawToolOutput, ToolRunner protocol
│   ├── runners/
│   │   ├── __init__.py
│   │   └── example.py                             # ExampleGitLogRunner (throwaway, removed at 2.1)
│   ├── taxonomy/
│   │   ├── __init__.py
│   │   ├── quality_framework_v1_0.yaml            # full 15-category/51-criterion catalog
│   │   └── seed.py                                # seed_taxonomy (idempotent)
│   └── orchestrator.py                            # AuditPlan, plan_audit, execute_audit
└── tests/
    ├── conftest.py                                # db_session fixture (reuses radar-core's Alembic)
    ├── git_helpers.py                              # init_git_repo test helper
    ├── test_config.py
    ├── test_discovery.py
    ├── test_worktree.py
    ├── test_runner.py
    ├── test_taxonomy_seed.py
    ├── test_orchestrator.py
    └── test_cli.py
```

Each module has one responsibility: `config.py` only parses/validates `portfolio.yaml`; `discovery.py` only finds sub-projects; `worktree.py` only computes the exclusion list; `runner.py` only defines the tool-execution contract; `orchestrator.py` is the sole module that composes the others into a full audit run. `cli.py` is a thin argument-parsing/wiring layer with no business logic of its own.

---

### Task 1: Workspace scaffolding

**Files:**
- Modify: `pyproject.toml` (root)
- Modify: `.pre-commit-config.yaml`
- Create: `radar-audit/pyproject.toml`
- Create: `radar-audit/src/radar_audit/__init__.py`
- Create: `radar-audit/tests/__init__.py` (empty, makes the tests package importable if needed by later relative imports — matches `radar-core/tests/models/__init__.py` precedent)
- Test: `radar-audit/tests/test_package.py`

**Interfaces:**
- Produces: an installable `radar_audit` package (`import radar_audit` succeeds), a working `uv sync` across both workspace members, ruff/mypy wired for `radar-audit/`.

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_package.py`:
```python
import radar_audit


def test_package_is_importable():
    assert radar_audit is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_package.py -v`
Expected: FAIL — `radar-audit` isn't a workspace member yet / `radar_audit` module doesn't exist (command itself will error: no `radar-audit` package to run `uv run` against). This is expected at this point; proceed to scaffolding.

- [ ] **Step 3: Create the package files**

`radar-audit/src/radar_audit/__init__.py`:
```python
```
(empty file)

`radar-audit/tests/__init__.py`:
```python
```
(empty file)

`radar-audit/pyproject.toml`:
```toml
[project]
name = "radar-audit"
version = "0.1.0"
description = "Tool orchestration and normalization engine for Portfolio-Engineering-Radar."
requires-python = ">=3.12"
dependencies = [
    "radar-core",
    "typer>=0.12",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "mypy>=1.11",
    "types-pyyaml>=6.0",
]

[tool.uv.sources]
radar-core = { workspace = true }

[project.scripts]
radar-audit = "radar_audit.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/radar_audit"]
```

Modify root `pyproject.toml`, changing:
```toml
[tool.uv.workspace]
members = ["radar-core"]
```
to:
```toml
[tool.uv.workspace]
members = ["radar-core", "radar-audit"]
```

Modify `.pre-commit-config.yaml` to:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
        files: ^(radar-core|radar-audit)/
      - id: ruff-format
        files: ^(radar-core|radar-audit)/
  - repo: local
    hooks:
      - id: mypy-radar-core
        name: mypy (radar-core)
        entry: uv run --package radar-core mypy radar-core/src/radar_core
        language: system
        files: ^radar-core/src/
        pass_filenames: false
      - id: mypy-radar-audit
        name: mypy (radar-audit)
        entry: uv run --package radar-audit mypy radar-audit/src/radar_audit
        language: system
        files: ^radar-audit/src/
        pass_filenames: false
```

Note: `cli.py` doesn't exist yet (Task 10 creates it), so the `[project.scripts]` entry point will not resolve until then — this is fine, it does not block `uv sync` or `pytest` for this task, only `uv run radar-audit` as a console script (unused before Task 10).

- [ ] **Step 4: Sync the workspace and run the test to verify it passes**

Run: `uv sync` (from repo root)
Run: `cd radar-audit && uv run pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml radar-audit/pyproject.toml radar-audit/src/radar_audit/__init__.py radar-audit/tests/__init__.py radar-audit/tests/test_package.py
git commit -m "chore(radar-audit): scaffold workspace package"
```

---

### Task 2: Test infrastructure — git fixture helper and DB session fixture

**Files:**
- Create: `radar-audit/tests/git_helpers.py`
- Create: `radar-audit/tests/conftest.py`
- Test: `radar-audit/tests/test_conftest_infra.py`

**Interfaces:**
- Produces: `init_git_repo(path: Path, files: dict[str, str] | None = None) -> None` (git_helpers.py) — used by Tasks 4, 5, 6, 8, 9, 11. `db_session` pytest fixture (conftest.py, function-scoped) — a `sqlmodel.Session` bound to a fresh SQLite file with `radar-core`'s Alembic migrations already applied — used by Tasks 7, 8, 9, 11.
- Consumes: `radar_core.db.get_engine` (existing, `radar-core/src/radar_core/db.py`).

- [ ] **Step 1: Write the failing test**

This task's own deliverable IS the test infrastructure other tasks will use, so the test is written directly against `git_helpers.py` and the `db_session` fixture:

`radar-audit/tests/test_conftest_infra.py`:
```python
import subprocess

from radar_core.models.repository import Repository
from sqlmodel import select

from tests.git_helpers import init_git_repo


def test_init_git_repo_creates_a_repo_with_one_commit(tmp_path):
    repo_path = tmp_path / "sample-repo"
    init_git_repo(repo_path)

    log = subprocess.run(
        ["git", "-C", str(repo_path), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log.stdout.strip().splitlines()) == 1


def test_init_git_repo_writes_requested_files(tmp_path):
    repo_path = tmp_path / "sample-repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname = 'x'\n"})

    assert (repo_path / "pyproject.toml").read_text() == "[project]\nname = 'x'\n"


def test_db_session_fixture_has_migrated_schema(db_session):
    repository = Repository(name="example", path="/tmp/example")
    db_session.add(repository)
    db_session.commit()

    found = db_session.exec(select(Repository).where(Repository.name == "example")).first()
    assert found is not None
    assert found.path == "/tmp/example"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_conftest_infra.py -v`
Expected: FAIL — `tests.git_helpers` doesn't exist, `db_session` fixture isn't defined.

- [ ] **Step 3: Implement the test infrastructure**

`radar-audit/tests/git_helpers.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(path: Path, files: dict[str, str] | None = None) -> None:
    """Create a git repo with one commit at `path`, for use as a test fixture.

    `path` must not already exist. `files` maps relative file paths (created
    with any needed parent directories) to their text content.
    """
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)

    for relative_path, content in (files or {}).items():
        file_path = path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    if not files:
        (path / ".gitkeep").touch()

    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=path, check=True)
```

`radar-audit/tests/conftest.py`:
```python
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from radar_core.db import get_engine
from sqlmodel import Session

RADAR_CORE_ROOT = Path(__file__).resolve().parents[2] / "radar-core"
ALEMBIC_INI = RADAR_CORE_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = RADAR_CORE_ROOT / "alembic"


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    previous_url = os.environ.get("RADAR_DATABASE_URL")
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_url is None:
            del os.environ["RADAR_DATABASE_URL"]
        else:
            os.environ["RADAR_DATABASE_URL"] = previous_url


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_conftest_infra.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/tests/git_helpers.py radar-audit/tests/conftest.py radar-audit/tests/test_conftest_infra.py
git commit -m "test(radar-audit): add git fixture helper and migrated db_session fixture"
```

---

### Task 3: Config loading — `portfolio.yaml`

**Files:**
- Create: `radar-audit/src/radar_audit/config.py`
- Create: `radar-audit/portfolio.yaml`
- Test: `radar-audit/tests/test_config.py`

**Interfaces:**
- Produces: `PortfolioConfigError(ValueError)`, `PortfolioConfig` (frozen dataclass: `repos_root: Path`, `repositories: list[str]`, method `resolve_repo_path(name: str) -> Path`), `load_portfolio_config(path: Path) -> PortfolioConfig` — consumed by Task 8 (`orchestrator.py`) and Task 10 (`cli.py`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_config.py`:
```python
import pytest

from radar_audit.config import PortfolioConfigError, load_portfolio_config


def _write_yaml(tmp_path, content):
    path = tmp_path / "portfolio.yaml"
    path.write_text(content)
    return path


def test_load_portfolio_config_reads_repos_root_and_repositories(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
        repos_root: /home/example/projets
        repositories:
          - name: RepoOne
          - name: RepoTwo
        """,
    )

    config = load_portfolio_config(path)

    assert config.repos_root == __import__("pathlib").Path("/home/example/projets")
    assert config.repositories == ["RepoOne", "RepoTwo"]


def test_load_portfolio_config_expands_user_in_repos_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = _write_yaml(
        tmp_path,
        """
        repos_root: ~/projets
        repositories:
          - name: RepoOne
        """,
    )

    config = load_portfolio_config(path)

    assert config.repos_root == tmp_path / "projets"


def test_load_portfolio_config_missing_repos_root_raises(tmp_path):
    path = _write_yaml(tmp_path, "repositories:\n  - name: RepoOne\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_load_portfolio_config_missing_repositories_raises(tmp_path):
    path = _write_yaml(tmp_path, "repos_root: /home/example/projets\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_load_portfolio_config_empty_repositories_raises(tmp_path):
    path = _write_yaml(tmp_path, "repos_root: /home/example/projets\nrepositories: []\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_resolve_repo_path_returns_repos_root_joined_with_name(tmp_path):
    path = _write_yaml(
        tmp_path,
        f"""
        repos_root: {tmp_path}
        repositories:
          - name: RepoOne
        """,
    )
    config = load_portfolio_config(path)

    assert config.resolve_repo_path("RepoOne") == (tmp_path / "RepoOne").resolve()


def test_resolve_repo_path_unknown_repo_raises(tmp_path):
    path = _write_yaml(
        tmp_path,
        f"""
        repos_root: {tmp_path}
        repositories:
          - name: RepoOne
        """,
    )
    config = load_portfolio_config(path)

    with pytest.raises(PortfolioConfigError):
        config.resolve_repo_path("Unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_config.py -v`
Expected: FAIL — `radar_audit.config` doesn't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/config.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PortfolioConfigError(ValueError):
    """Raised when portfolio.yaml is missing required fields or malformed."""


@dataclass(frozen=True)
class PortfolioConfig:
    repos_root: Path
    repositories: list[str]

    def resolve_repo_path(self, name: str) -> Path:
        if name not in self.repositories:
            raise PortfolioConfigError(f"Repository '{name}' is not listed in portfolio.yaml")
        return (self.repos_root / name).resolve()


def load_portfolio_config(path: Path) -> PortfolioConfig:
    raw: Any = yaml.safe_load(path.read_text())

    if not isinstance(raw, dict) or "repos_root" not in raw:
        raise PortfolioConfigError(f"{path} must define 'repos_root'")
    if "repositories" not in raw or not raw["repositories"]:
        raise PortfolioConfigError(f"{path} must define a non-empty 'repositories' list")

    repos_root = Path(str(raw["repos_root"])).expanduser()
    repositories = [str(entry["name"]) for entry in raw["repositories"]]

    return PortfolioConfig(repos_root=repos_root, repositories=repositories)
```

`radar-audit/portfolio.yaml` (the real, versioned config — D1's confirmed 10-repo scope):
```yaml
repos_root: ~/projets
repositories:
  - name: CC-Beacon
  - name: GeoChallenge-Tracker
  - name: HexaRot
  - name: HiveMind
  - name: JobFlow
  - name: Portfolio-Engineering-Radar
  - name: Stamped
  - name: Summit-Stats
  - name: Trello-Board-Init
  - name: Triton
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_config.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/config.py radar-audit/portfolio.yaml radar-audit/tests/test_config.py
git commit -m "feat(radar-audit): add portfolio.yaml loading and validation"
```

---

### Task 4: Sub-project discovery

**Files:**
- Create: `radar-audit/src/radar_audit/discovery.py`
- Test: `radar-audit/tests/test_discovery.py`

**Interfaces:**
- Consumes: `tests.git_helpers.init_git_repo` (Task 2).
- Produces: `SubProject` (frozen dataclass: `path: Path`, `stack: str`), `discover_subprojects(repo_path: Path) -> list[SubProject]` — consumed by Task 8 (`orchestrator.py`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_discovery.py`:
```python
from radar_audit.discovery import SubProject, discover_subprojects
from tests.git_helpers import init_git_repo


def test_single_python_repo_yields_one_subproject_at_root(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname='x'\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="python")]


def test_repo_with_no_manifest_yields_one_unknown_subproject(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="unknown")]


def test_monorepo_with_first_level_manifests_yields_one_subproject_per_dir(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "backend/pyproject.toml": "[project]\nname='backend'\n",
            "frontend/package.json": "{}\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert sorted(result, key=lambda sp: sp.path) == sorted(
        [
            SubProject(path=repo_path / "backend", stack="python"),
            SubProject(path=repo_path / "frontend", stack="javascript"),
        ],
        key=lambda sp: sp.path,
    )


def test_root_and_first_level_manifests_both_detected(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pyproject.toml": "[project]\nname='root'\n",
            "radar-core/pyproject.toml": "[project]\nname='radar-core'\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert sorted(result, key=lambda sp: sp.path) == sorted(
        [
            SubProject(path=repo_path, stack="python"),
            SubProject(path=repo_path / "radar-core", stack="python"),
        ],
        key=lambda sp: sp.path,
    )


def test_php_manifest_detected(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"composer.json": "{}\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="php")]


def test_requirements_txt_maps_to_python_and_does_not_duplicate(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pyproject.toml": "[project]\nname='x'\n",
            "requirements.txt": "requests\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="python")]


def test_dot_directories_are_ignored(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "README.md": "hello\n",
            ".venv/pyvenv.cfg": "home = /usr\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="unknown")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_discovery.py -v`
Expected: FAIL — `radar_audit.discovery` doesn't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/discovery.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_MANIFEST_STACKS: dict[str, str] = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "javascript",
    "composer.json": "php",
}


@dataclass(frozen=True)
class SubProject:
    path: Path
    stack: str


def discover_subprojects(repo_path: Path) -> list[SubProject]:
    subprojects = [
        SubProject(path=repo_path, stack=stack) for stack in _manifests_at(repo_path)
    ]

    for child in sorted(p for p in repo_path.iterdir() if p.is_dir() and not p.name.startswith(".")):
        subprojects.extend(SubProject(path=child, stack=stack) for stack in _manifests_at(child))

    if not subprojects:
        return [SubProject(path=repo_path, stack="unknown")]

    return subprojects


def _manifests_at(directory: Path) -> list[str]:
    stacks: list[str] = []
    for manifest_name, stack in _MANIFEST_STACKS.items():
        if (directory / manifest_name).is_file() and stack not in stacks:
            stacks.append(stack)
    return stacks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_discovery.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/discovery.py radar-audit/tests/test_discovery.py
git commit -m "feat(radar-audit): add manifest-based sub-project discovery"
```

---

### Task 5: Worktree exclusion

**Files:**
- Create: `radar-audit/src/radar_audit/worktree.py`
- Test: `radar-audit/tests/test_worktree.py`

**Interfaces:**
- Consumes: `tests.git_helpers.init_git_repo` (Task 2).
- Produces: `compute_exclude_paths(repo_path: Path) -> list[Path]` — consumed by Task 8 (`orchestrator.py`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_worktree.py`:
```python
import subprocess

from radar_audit.worktree import compute_exclude_paths
from tests.git_helpers import init_git_repo


def test_repo_with_no_extra_worktrees_returns_empty_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert compute_exclude_paths(repo_path) == []


def test_repo_with_a_worktree_excludes_it(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert result == [worktree_path.resolve()]


def test_main_repo_path_itself_is_never_in_the_exclude_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert repo_path.resolve() not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_worktree.py -v`
Expected: FAIL — `radar_audit.worktree` doesn't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/worktree.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path


def compute_exclude_paths(repo_path: Path) -> list[Path]:
    """Return every worktree path linked to `repo_path`'s repo, excluding `repo_path` itself."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )

    all_paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]

    main_path = repo_path.resolve()
    return [path for path in all_paths if path != main_path]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_worktree.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/worktree.py radar-audit/tests/test_worktree.py
git commit -m "feat(radar-audit): compute worktree exclusion list via git worktree list"
```

---

### Task 6: ToolRunner abstraction and example runner

**Files:**
- Create: `radar-audit/src/radar_audit/runner.py`
- Create: `radar-audit/src/radar_audit/runners/__init__.py`
- Create: `radar-audit/src/radar_audit/runners/example.py`
- Test: `radar-audit/tests/test_runner.py`

**Interfaces:**
- Consumes: `tests.git_helpers.init_git_repo` (Task 2).
- Produces: `RawToolOutput` (frozen dataclass: `command: str`, `raw_output: dict[str, object]`, `exit_code: int`, `duration_ms: int`), `ToolRunner` (`Protocol`: `tool_name: str`, `tool_version: str`, `run(subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput`), `ExampleGitLogRunner` (implements `ToolRunner`, `tool_name = "example-git-log"`, `tool_version = "1.0.0"`) — consumed by Task 8/9 (`orchestrator.py`), Task 10 (`cli.py`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_runner.py`:
```python
from radar_audit.runners.example import ExampleGitLogRunner
from tests.git_helpers import init_git_repo


def test_example_runner_reports_head_commit_sha(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    runner = ExampleGitLogRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert len(result.raw_output["stdout"]) == 40  # full SHA-1
    assert result.raw_output["stderr"] == ""
    assert result.duration_ms >= 0


def test_example_runner_reports_tool_identity():
    runner = ExampleGitLogRunner()

    assert runner.tool_name == "example-git-log"
    assert runner.tool_version == "1.0.0"


def test_example_runner_nonzero_exit_on_non_git_directory(tmp_path):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()

    runner = ExampleGitLogRunner()
    result = runner.run(not_a_repo, exclude_paths=[])

    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_runner.py -v`
Expected: FAIL — `radar_audit.runner` and `radar_audit.runners.example` don't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/runner.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RawToolOutput:
    command: str
    raw_output: dict[str, object]
    exit_code: int
    duration_ms: int


class ToolRunner(Protocol):
    tool_name: str
    tool_version: str

    def run(self, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput: ...
```

`radar-audit/src/radar_audit/runners/__init__.py`:
```python
```
(empty file)

`radar-audit/src/radar_audit/runners/example.py`:
```python
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from radar_audit.runner import RawToolOutput


class ExampleGitLogRunner:
    """Throwaway proof-of-pipeline runner. Removed once increment 2.1 adds real tools."""

    tool_name = "example-git-log"
    tool_version = "1.0.0"

    def run(self, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["git", "-C", str(subproject_path), "log", "-1", "--format=%H"]
        start = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True)
        duration_ms = int((time.monotonic() - start) * 1000)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_runner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runner.py radar-audit/src/radar_audit/runners/ radar-audit/tests/test_runner.py
git commit -m "feat(radar-audit): add ToolRunner protocol and throwaway example runner"
```

---

### Task 7: Taxonomy — full catalog YAML and idempotent seed function

**Files:**
- Create: `radar-audit/src/radar_audit/taxonomy/__init__.py`
- Create: `radar-audit/src/radar_audit/taxonomy/quality_framework_v1_0.yaml`
- Create: `radar-audit/src/radar_audit/taxonomy/seed.py`
- Test: `radar-audit/tests/test_taxonomy_seed.py`
- Test fixture: `radar-audit/tests/fixtures/taxonomy_sample.yaml`

**Interfaces:**
- Consumes: `db_session` fixture (Task 2), `radar_core.enums.ScoringModel`, `radar_core.models.methodology.{MethodologyVersion, Category, Criterion}` (existing).
- Produces: `TAXONOMY_PATH: Path` (points at `quality_framework_v1_0.yaml`), `seed_taxonomy(session: Session, yaml_path: Path = TAXONOMY_PATH) -> MethodologyVersion` — consumed by Task 9 (`orchestrator.py`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/fixtures/taxonomy_sample.yaml` (a small fixture for unit-testing seeding mechanics, independent of the real catalog's size):
```yaml
version_label: "Sample Taxonomy v0.1"
notes: "Fixture for seed_taxonomy unit tests"
categories:
  - name: "Sample category A"
    order: 1
    weight: 50.0
    criteria:
      - name: "Sample criterion A1"
        description: "Fixture criterion, fixed-scale"
        weight: 50.0
        scoring_model: FIXED_SCALE
      - name: "Sample criterion A2"
        description: "Fixture criterion, status 4-state"
        weight: 50.0
        scoring_model: STATUS_4STATE
  - name: "Sample category B"
    order: 2
    weight: 50.0
    criteria:
      - name: "Sample criterion B1"
        description: "Fixture criterion, fixed-scale"
        weight: 100.0
        scoring_model: FIXED_SCALE
```

`radar-audit/tests/test_taxonomy_seed.py`:
```python
from pathlib import Path

from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from sqlmodel import select

from radar_audit.taxonomy.seed import TAXONOMY_PATH, seed_taxonomy

SAMPLE_YAML = Path(__file__).parent / "fixtures" / "taxonomy_sample.yaml"


def test_seed_taxonomy_creates_version_categories_and_criteria(db_session):
    seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)

    version = db_session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == "Sample Taxonomy v0.1")
    ).first()
    assert version is not None

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == version.id)
    ).all()
    assert len(categories) == 2

    criteria = db_session.exec(
        select(Criterion).where(Criterion.category_id.in_([c.id for c in categories]))
    ).all()
    assert len(criteria) == 3
    assert {c.scoring_model for c in criteria} == {ScoringModel.FIXED_SCALE, ScoringModel.STATUS_4STATE}


def test_seed_taxonomy_is_idempotent(db_session):
    first = seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)
    second = seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)

    assert first.id == second.id

    versions = db_session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == "Sample Taxonomy v0.1")
    ).all()
    assert len(versions) == 1

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == first.id)
    ).all()
    assert len(categories) == 2


def test_seed_taxonomy_default_path_loads_the_real_catalog(db_session):
    version = seed_taxonomy(db_session)

    assert version.version_label == "Quality Framework v1.0"

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == version.id)
    ).all()
    assert len(categories) == 15

    criteria = db_session.exec(
        select(Criterion).where(Criterion.category_id.in_([c.id for c in categories]))
    ).all()
    assert len(criteria) == 51

    for category in categories:
        category_criteria = [c for c in criteria if c.category_id == category.id]
        assert len(category_criteria) > 0

    total_category_weight = sum(c.weight for c in categories)
    assert abs(total_category_weight - 100.0) < 0.2

    assert TAXONOMY_PATH.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_taxonomy_seed.py -v`
Expected: FAIL — `radar_audit.taxonomy.seed` doesn't exist, `quality_framework_v1_0.yaml` doesn't exist.

- [ ] **Step 3: Write the taxonomy YAML and the seed implementation**

`radar-audit/src/radar_audit/taxonomy/__init__.py`:
```python
```
(empty file)

`radar-audit/src/radar_audit/taxonomy/quality_framework_v1_0.yaml` — full transcription of `docs/quality-framework.md`§4 (15 categories, 51 criteria). Category weights: Security and Testing & reliability at `10.0`, the remaining 13 categories at `6.15` each (≈80/13, per `docs/quality-framework.md`§3.1 — the `99.95` sum this produces is the source document's own rounding, not an error). Criterion weights are equal within each category, expressed so they sum to `100.0` per category (`100 / n`, rounded to 2 decimals). `scoring_model` maps archetype A and B to `FIXED_SCALE`, archetype C to `STATUS_4STATE` (`docs/quality-framework.md`§2). Two catalog entries whose Archetype column is `—` (not A/B/C) are cross-referenced evidence only, not independently scored, and are excluded as separate `Criterion` rows: **10.3** (Accessibility/WCAG, folded into 10.1's evidence per its own note "Not a separate criterion, avoids double-counting") and **12.1** (Secrets never hardcoded, folded into 4.2's evidence). Backend/DB performance (§4.6) has no criterion in v1.0 at all — category 6 has exactly one criterion (6.1, Frontend performance).

```yaml
version_label: "Quality Framework v1.0"
notes: "Frozen 2026-08-26, see docs/quality-framework.md"
categories:
  - name: "Architecture & design"
    order: 1
    weight: 6.15
    criteria:
      - name: "Dependency direction / circularity"
        description: "dependency-cruiser (JS/TS), pydeps (Python) — cycle count. 0 cycles=10, 1-2=6, 3-5=4, >5=2"
        weight: 25.0
        scoring_model: FIXED_SCALE
      - name: "Architectural documentation present"
        description: "DESIGN.md/ARCHITECTURE.md/ADR presence and non-trivial length"
        weight: 25.0
        scoring_model: FIXED_SCALE
      - name: "Module size distribution"
        description: "radon (Python LOC/complexity proxy); JS/PHP: no dedicated tool validated yet, static LOC count only"
        weight: 25.0
        scoring_model: FIXED_SCALE
      - name: "Consistency of architectural style"
        description: "Narrow LLM-judgment layer, restricted to single dominant style vs. visibly mixed"
        weight: 25.0
        scoring_model: FIXED_SCALE
  - name: "Code quality"
    order: 2
    weight: 6.15
    criteria:
      - name: "Linter clean pass rate"
        description: "Ruff / ESLint / PHPStan, findings vs. files scanned"
        weight: 20.0
        scoring_model: FIXED_SCALE
      - name: "Type-checking pass"
        description: "mypy / tsc --noEmit / PHPStan"
        weight: 20.0
        scoring_model: FIXED_SCALE
      - name: "Cyclomatic complexity"
        description: "radon (Python, validated). JS: ESLint complexity rule (candidate). PHP: PHPMD codesize ruleset (candidate)"
        weight: 20.0
        scoring_model: FIXED_SCALE
      - name: "Pre-commit quality gate"
        description: "Pre-commit/CI lint-format-typecheck hooks configured (D12): DONE / IN_PROGRESS / TODO"
        weight: 20.0
        scoring_model: STATUS_4STATE
      - name: "Code duplication"
        description: "jscpd (candidate, single tool covering Python/JS-TS/PHP/Vue)"
        weight: 20.0
        scoring_model: FIXED_SCALE
  - name: "Testing & reliability"
    order: 3
    weight: 10.0
    criteria:
      - name: "Unit tests present & passing, with coverage"
        description: "pytest+coverage / Vitest / Pest, pass rate and coverage %"
        weight: 20.0
        scoring_model: FIXED_SCALE
      - name: "Integration tests"
        description: "Heuristic: test files under an integration-named path, or importing DB/HTTP layers"
        weight: 20.0
        scoring_model: FIXED_SCALE
      - name: "E2E tests"
        description: "Playwright present & wired into CI = DONE; present but not in CI = IN_PROGRESS; absent = TODO for web-facing repos, N/A for non-UI repos"
        weight: 20.0
        scoring_model: STATUS_4STATE
      - name: "CI executes the test suite"
        description: "actionlint-derived: a workflow step invokes pytest/Vitest/Pest"
        weight: 20.0
        scoring_model: STATUS_4STATE
      - name: "Test quality / relevance"
        description: "Narrow LLM-judgment layer (meaningful vs. tautological assertions)"
        weight: 20.0
        scoring_model: FIXED_SCALE
  - name: "Security"
    order: 4
    weight: 10.0
    criteria:
      - name: "Dependency vulnerabilities (CVE)"
        description: "pip-audit / pnpm audit / composer audit, severity-tiered. Feeds critical penalty P1 (docs/quality-framework.md 3.2)"
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "Secrets in tracked history"
        description: "Gitleaks, git-history mode. Feeds critical penalty P1 (docs/quality-framework.md 3.2)"
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "SAST findings"
        description: "Semgrep, severity-tiered"
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "Container image vulnerabilities"
        description: "Trivy image scan, HIGH/CRITICAL count. N/A if no locally built image."
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "Dockerfile hardening"
        description: "Hadolint findings density"
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "AuthN/authZ hygiene"
        description: "Semgrep registry authN/authZ rulesets (p/security-audit + framework-specific packs), candidate"
        weight: 14.29
        scoring_model: FIXED_SCALE
      - name: "HTTP security headers"
        description: "mdn-http-observatory (candidate, runtime check); fallback candidate shcheck (presence-only)"
        weight: 14.29
        scoring_model: FIXED_SCALE
  - name: "Maintainability"
    order: 5
    weight: 6.15
    criteria:
      - name: "Complexity hotspots"
        description: "Shares evidence with cyclomatic complexity (2.3), distinct framing: flags outlier files rather than the repo-wide average"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Dead code / unused exports"
        description: "knip (JS, validated). Python: vulture (candidate). PHP: PHPMD unusedcode ruleset (candidate)"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Documentation-in-code (docstring/comment coverage)"
        description: "Python: docvet (candidate). PHP: php-censor/phpdoc-checker (candidate). JS/TS: no candidate identified"
        weight: 33.33
        scoring_model: FIXED_SCALE
  - name: "Performance"
    order: 6
    weight: 6.15
    criteria:
      - name: "Frontend performance"
        description: "Lighthouse, score-tiered (90-100=10, 70-89=6-8, 50-69=4, <50=2/0). N/A for repos with no UI. Candidate, not yet smoke-tested. Backend/DB performance has no criterion in v1.0, deliberately excluded (docs/quality-framework.md 4.6)."
        weight: 100.0
        scoring_model: FIXED_SCALE
  - name: "DevOps / CI-CD"
    order: 7
    weight: 6.15
    criteria:
      - name: "CI presence & health"
        description: "GH Actions workflow present + actionlint clean"
        weight: 25.0
        scoring_model: FIXED_SCALE
      - name: "Reverse proxy / local-prod environment parity (Traefik)"
        description: "See docs/system-design.md D11 — reverse proxy / local-prod parity presence"
        weight: 25.0
        scoring_model: STATUS_4STATE
      - name: "Container build hardening"
        description: "Shares evidence with 4.4/4.5, DevOps framing (is the pipeline clean) vs. Security framing (is the image vulnerable)"
        weight: 25.0
        scoring_model: FIXED_SCALE
      - name: "Deployment automation"
        description: "build-push.yml/build-deploy.yml presence, wired to a registry push step"
        weight: 25.0
        scoring_model: STATUS_4STATE
  - name: "Documentation"
    order: 8
    weight: 6.15
    criteria:
      - name: "README completeness"
        description: "Heuristic: standard section headers present (setup, usage, architecture overview)"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Architecture documentation"
        description: "Shares evidence with 1.2, Documentation framing (present and readable) vs. Architecture framing (reflects real structure)"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "API documentation"
        description: "OpenAPI/Swagger schema present & served (FastAPI auto-docs, Laravel L5-Swagger). N/A for repos with no API."
        weight: 33.33
        scoring_model: STATUS_4STATE
  - name: "Observability / operations"
    order: 9
    weight: 6.15
    criteria:
      - name: "Structured logging"
        description: "Heuristic: structured logging library/formatter vs. bare print/console.log"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Error tracking integration"
        description: "Sentry SDK (or equivalent) present & configured"
        weight: 33.33
        scoring_model: STATUS_4STATE
      - name: "Health-check endpoint"
        description: "/health or /healthz route present. N/A for repos with no long-lived service."
        weight: 33.33
        scoring_model: STATUS_4STATE
  - name: "API / UX / product quality"
    order: 10
    weight: 6.15
    criteria:
      - name: "Graphic/visual design quality"
        description: "See docs/system-design.md D13 — narrow LLM-judgment layer on visual design. Also covers accessibility/WCAG as part of its factual layer (docs/quality-framework.md 4.10, criterion 10.3 is not separately scored)."
        weight: 50.0
        scoring_model: FIXED_SCALE
      - name: "API contract consistency"
        description: "Spectral, built-in spectral:oas ruleset (candidate). Needs an exported OpenAPI spec file."
        weight: 50.0
        scoring_model: FIXED_SCALE
  - name: "Dependency management"
    order: 11
    weight: 6.15
    criteria:
      - name: "Dependency freshness"
        description: "pip list --outdated / npm & pnpm outdated / composer outdated. Gated behind D15 opt-in registry access; N/A when access isn't granted, and N/A for unpinned repos with no lock file."
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "License compliance"
        description: "Python: pip-licenses (candidate). JS: license-checker-evergreen (candidate). PHP: composer licenses --format=json (validated)"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Dependency footprint"
        description: "Raw dependency count relative to repo size. No established baseline yet, needs Phase 3 calibration data."
        weight: 33.33
        scoring_model: FIXED_SCALE
  - name: "Configuration management"
    order: 12
    weight: 6.15
    criteria:
      - name: "Environment separation"
        description: "Heuristic: distinct .env.example/.env.testing/.env.prod.example or equivalent. Also covers 'secrets never hardcoded' as part of its evidence (docs/quality-framework.md 4.12, criterion 12.1 is not separately scored — cross-referenced from 4.2)."
        weight: 50.0
        scoring_model: FIXED_SCALE
      - name: "Config validation at startup"
        description: "Heuristic: Pydantic Settings (Python) / Laravel config validation pattern present"
        weight: 50.0
        scoring_model: STATUS_4STATE
  - name: "Data quality"
    order: 13
    weight: 6.15
    criteria:
      - name: "Schema/migration versioning"
        description: "Migrations directory with sequential, timestamped files (Laravel, Alembic, Django)"
        weight: 33.33
        scoring_model: STATUS_4STATE
      - name: "Input validation at boundaries"
        description: "Heuristic: Pydantic models on FastAPI routes / Laravel FormRequest classes"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Test data / fixtures quality"
        description: "Faker/factory pattern present for tests vs. hardcoded literals"
        weight: 33.33
        scoring_model: STATUS_4STATE
  - name: "Developer experience"
    order: 14
    weight: 6.15
    criteria:
      - name: "Onboarding documentation"
        description: "CONTRIBUTING.md / setup script presence"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Local dev reproducibility"
        description: "Shares evidence with reverse proxy / local-prod parity (D11) plus Docker Compose dev-profile presence"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Script/task standardization"
        description: "package.json/composer.json scripts or Makefile covering the common lifecycle (dev, test, lint, build)"
        weight: 33.33
        scoring_model: FIXED_SCALE
  - name: "Technical debt"
    order: 15
    weight: 6.15
    criteria:
      - name: "TODO/FIXME density"
        description: "Grep-based count, normalized per KLOC"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Dead/unreachable code"
        description: "Shares evidence with dead code / unused exports (5.2)"
        weight: 33.33
        scoring_model: FIXED_SCALE
      - name: "Framework/runtime version currency"
        description: "Engine version pinned vs. actually running"
        weight: 33.33
        scoring_model: FIXED_SCALE
```

`radar-audit/src/radar_audit/taxonomy/seed.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from sqlmodel import Session, select

TAXONOMY_PATH = Path(__file__).parent / "quality_framework_v1_0.yaml"


def seed_taxonomy(session: Session, yaml_path: Path = TAXONOMY_PATH) -> MethodologyVersion:
    """Seed a MethodologyVersion + its Categories/Criteria from `yaml_path`, once.

    If a MethodologyVersion with the same version_label already exists, it is
    returned as-is and nothing is re-inserted.
    """
    data: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
    version_label = data["version_label"]

    existing = session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == version_label)
    ).first()
    if existing is not None:
        return existing

    methodology_version = MethodologyVersion(version_label=version_label, notes=data.get("notes"))
    session.add(methodology_version)
    session.flush()

    for category_data in data["categories"]:
        category = Category(
            methodology_version_id=methodology_version.id,
            name=category_data["name"],
            weight=category_data["weight"],
            order=category_data["order"],
        )
        session.add(category)
        session.flush()

        for criterion_data in category_data["criteria"]:
            criterion = Criterion(
                category_id=category.id,
                name=criterion_data["name"],
                description=criterion_data["description"],
                weight=criterion_data["weight"],
                scoring_model=ScoringModel(criterion_data["scoring_model"]),
            )
            session.add(criterion)

    session.commit()
    session.refresh(methodology_version)
    return methodology_version
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_taxonomy_seed.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/taxonomy/ radar-audit/tests/test_taxonomy_seed.py radar-audit/tests/fixtures/taxonomy_sample.yaml
git commit -m "feat(radar-audit): seed Quality Framework v1.0 taxonomy idempotently"
```

---

### Task 8: Repository resolution and Audit creation

**Files:**
- Create: `radar-audit/src/radar_audit/orchestrator.py` (partial — this task's functions only)
- Test: `radar-audit/tests/test_orchestrator.py` (partial — this task's tests only; Task 9 extends both files)

**Interfaces:**
- Consumes: `db_session` fixture, `tests.git_helpers.init_git_repo` (Task 2); `radar_core.models.repository.Repository`, `radar_core.models.audit.Audit` (existing).
- Produces: `resolve_repository(session: Session, repo_path: Path, repo_name: str) -> Repository`, `get_commit_sha(repo_path: Path) -> str`, `is_dirty(repo_path: Path) -> bool`, `get_or_create_audit(session: Session, repository: Repository) -> Audit` — consumed by Task 9 (same file, `execute_audit`).

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_orchestrator.py`:
```python
from radar_core.models.repository import Repository
from sqlmodel import select

from radar_audit.orchestrator import get_commit_sha, get_or_create_audit, is_dirty, resolve_repository
from tests.git_helpers import init_git_repo


def test_resolve_repository_creates_a_new_repository(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    repository = resolve_repository(db_session, repo_path, "repo")

    assert repository.id is not None
    assert repository.name == "repo"
    assert repository.path == str(repo_path)


def test_resolve_repository_reuses_existing_by_path(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    first = resolve_repository(db_session, repo_path, "repo")
    second = resolve_repository(db_session, repo_path, "repo")

    assert first.id == second.id
    all_repos = db_session.exec(select(Repository).where(Repository.path == str(repo_path))).all()
    assert len(all_repos) == 1


def test_get_commit_sha_returns_head_sha(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    sha = get_commit_sha(repo_path)

    assert len(sha) == 40


def test_is_dirty_false_on_clean_checkout(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert is_dirty(repo_path) is False


def test_is_dirty_true_with_uncommitted_changes(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})
    (repo_path / "README.md").write_text("modified\n")

    assert is_dirty(repo_path) is True


def test_get_or_create_audit_creates_a_new_audit(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    repository = resolve_repository(db_session, repo_path, "repo")

    audit = get_or_create_audit(db_session, repository)

    assert audit.id is not None
    assert audit.repository_id == repository.id
    assert audit.is_dirty is False


def test_get_or_create_audit_reuses_existing_clean_commit_audit(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    repository = resolve_repository(db_session, repo_path, "repo")

    first = get_or_create_audit(db_session, repository)
    second = get_or_create_audit(db_session, repository)

    assert first.id == second.id


def test_get_or_create_audit_creates_a_new_row_per_dirty_run(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})
    (repo_path / "README.md").write_text("modified\n")
    repository = resolve_repository(db_session, repo_path, "repo")

    first = get_or_create_audit(db_session, repository)
    second = get_or_create_audit(db_session, repository)

    assert first.id != second.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — `radar_audit.orchestrator` doesn't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/orchestrator.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

from radar_core.models.audit import Audit
from radar_core.models.repository import Repository
from sqlmodel import Session, select


def resolve_repository(session: Session, repo_path: Path, repo_name: str) -> Repository:
    existing = session.exec(select(Repository).where(Repository.path == str(repo_path))).first()
    if existing is not None:
        return existing

    repository = Repository(name=repo_name, path=str(repo_path))
    session.add(repository)
    session.commit()
    session.refresh(repository)
    return repository


def get_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def is_dirty(repo_path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def get_or_create_audit(session: Session, repository: Repository) -> Audit:
    """Create an Audit for the repo's current HEAD, reusing an existing one for the same
    clean commit (the DB enforces at most one clean-commit Audit per repo via a unique
    index — see radar_core/src/radar_core/models/audit.py). Every dirty-checkout run gets
    its own new Audit row, since dirty state isn't reproducible/comparable across runs.
    """
    repo_path = Path(repository.path)
    commit_sha = get_commit_sha(repo_path)
    dirty = is_dirty(repo_path)

    if not dirty:
        existing = session.exec(
            select(Audit).where(
                Audit.repository_id == repository.id,
                Audit.commit_sha == commit_sha,
                Audit.is_dirty.is_(False),
            )
        ).first()
        if existing is not None:
            return existing

    audit = Audit(repository_id=repository.id, commit_sha=commit_sha, is_dirty=dirty)
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/orchestrator.py radar-audit/tests/test_orchestrator.py
git commit -m "feat(radar-audit): resolve Repository and create/reuse Audit rows"
```

---

### Task 9: Full orchestration flow — plan_audit and execute_audit

**Files:**
- Modify: `radar-audit/src/radar_audit/orchestrator.py`
- Modify: `radar-audit/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `PortfolioConfig` (Task 3), `discover_subprojects`/`SubProject` (Task 4), `compute_exclude_paths` (Task 5), `RawToolOutput`/`ToolRunner` (Task 6), `seed_taxonomy` (Task 7), `resolve_repository`/`get_or_create_audit` (Task 8, same file).
- Produces: `AuditPlan` (frozen dataclass: `repository_name: str`, `repository_path: Path`, `subprojects: list[SubProject]`, `exclude_paths: list[Path]`), `plan_audit(config: PortfolioConfig, repo_name: str) -> AuditPlan`, `execute_audit(session: Session, config: PortfolioConfig, repo_name: str, runners: list[ToolRunner]) -> Audit` — consumed by Task 10 (`cli.py`), Task 11 (end-to-end test).

- [ ] **Step 1: Write the failing test**

Add to `radar-audit/tests/test_orchestrator.py`:
```python
from radar_core.models.audit import ToolResult
from radar_audit.config import PortfolioConfig
from radar_audit.orchestrator import AuditPlan, execute_audit, plan_audit
from radar_audit.runner import RawToolOutput


class _StubRunner:
    tool_name = "stub-runner"
    tool_version = "0.0.1"

    def run(self, subproject_path, exclude_paths):
        return RawToolOutput(
            command="stub",
            raw_output={"ok": True},
            exit_code=0,
            duration_ms=1,
        )


class _AlwaysCrashesRunner:
    tool_name = "crashes-runner"
    tool_version = "0.0.1"

    def run(self, subproject_path, exclude_paths):
        raise RuntimeError("boom")


def test_plan_audit_returns_repo_subprojects_and_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    plan = plan_audit(config, "repo")

    assert isinstance(plan, AuditPlan)
    assert plan.repository_name == "repo"
    assert plan.repository_path == repo_path.resolve()
    assert len(plan.subprojects) == 1
    assert plan.exclude_paths == []


def test_execute_audit_persists_one_tool_result_per_subproject_and_runner(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"backend/pyproject.toml": "[project]\nname='x'\n", "frontend/package.json": "{}\n"},
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_StubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert len(results) == 2
    assert all(r.tool_name == "stub-runner" for r in results)
    assert all(r.exit_code == 0 for r in results)


def test_execute_audit_continues_past_a_crashing_runner(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_AlwaysCrashesRunner(), _StubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert len(results) == 2

    crashed = next(r for r in results if r.tool_name == "crashes-runner")
    assert crashed.exit_code != 0
    assert "boom" in crashed.raw_output["error"]

    succeeded = next(r for r in results if r.tool_name == "stub-runner")
    assert succeeded.exit_code == 0


def test_execute_audit_seeds_the_taxonomy(db_session, tmp_path):
    from radar_core.models.methodology import MethodologyVersion

    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    execute_audit(db_session, config, "repo", [_StubRunner()])

    version = db_session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == "Quality Framework v1.0")
    ).first()
    assert version is not None
```

(This extends the existing test file — keep the imports already present at the top, e.g. `init_git_repo`, `select`, alongside these additions.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — `AuditPlan`, `plan_audit`, `execute_audit` don't exist yet.

- [ ] **Step 3: Extend the implementation**

Append to `radar-audit/src/radar_audit/orchestrator.py` (add these imports at the top alongside the existing ones, and these definitions at the bottom):

```python
from dataclasses import dataclass

from radar_core.models.audit import ToolResult

from radar_audit.config import PortfolioConfig
from radar_audit.discovery import SubProject, discover_subprojects
from radar_audit.runner import RawToolOutput, ToolRunner
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_audit.worktree import compute_exclude_paths


@dataclass(frozen=True)
class AuditPlan:
    repository_name: str
    repository_path: Path
    subprojects: list[SubProject]
    exclude_paths: list[Path]


def plan_audit(config: PortfolioConfig, repo_name: str) -> AuditPlan:
    repo_path = config.resolve_repo_path(repo_name)
    return AuditPlan(
        repository_name=repo_name,
        repository_path=repo_path,
        subprojects=discover_subprojects(repo_path),
        exclude_paths=compute_exclude_paths(repo_path),
    )


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

    for subproject in plan.subprojects:
        for runner in runners:
            raw = _run_tool_safely(runner, subproject.path, plan.exclude_paths)
            session.add(
                ToolResult(
                    audit_id=audit.id,
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


def _run_tool_safely(runner: ToolRunner, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
    try:
        return runner.run(subproject_path, exclude_paths)
    except Exception as exc:  # noqa: BLE001 — a tool crash must persist as evidence, never abort the audit
        return RawToolOutput(
            command=f"{runner.tool_name} (crashed)",
            raw_output={"error": str(exc)},
            exit_code=-1,
            duration_ms=0,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/orchestrator.py radar-audit/tests/test_orchestrator.py
git commit -m "feat(radar-audit): tie discovery, taxonomy, and tool execution into a full audit run"
```

---

### Task 10: CLI

**Files:**
- Create: `radar-audit/src/radar_audit/cli.py`
- Create: `radar-audit/README.md`
- Test: `radar-audit/tests/test_cli.py`

**Interfaces:**
- Consumes: `load_portfolio_config` (Task 3), `plan_audit`/`execute_audit`/`AuditPlan` (Task 9), `ExampleGitLogRunner` (Task 6), `radar_core.db.{get_engine, get_session}` (existing).
- Produces: `app: typer.Typer` (the `[project.scripts]` entry point target set in Task 1), `DEFAULT_RUNNERS: list[ToolRunner]`.

- [ ] **Step 1: Write the failing test**

`radar-audit/tests/test_cli.py`:
```python
from sqlmodel import Session, select
from typer.testing import CliRunner

from radar_audit.cli import app
from tests.conftest import RADAR_CORE_ROOT
from tests.git_helpers import init_git_repo

runner = CliRunner()


def _write_config(tmp_path, repos_root, repo_names):
    path = tmp_path / "portfolio.yaml"
    repos_yaml = "\n".join(f"  - name: {name}" for name in repo_names)
    path.write_text(f"repos_root: {repos_root}\nrepositories:\n{repos_yaml}\n")
    return path


def test_dry_run_prints_plan_and_writes_nothing_to_disk(tmp_path):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "sample-repo" in result.stdout
    assert "example-git-log" in result.stdout
    assert not (tmp_path / "radar.db").exists()


def test_run_without_repo_name_or_all_fails(tmp_path):
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    result = runner.invoke(app, ["run", "--config", str(config_path)])

    assert result.exit_code != 0


def test_real_run_persists_audit_and_tool_results(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")

    from alembic import command
    from alembic.config import Config

    alembic_config = Config(str(RADAR_CORE_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(RADAR_CORE_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")

    result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])

    assert result.exit_code == 0
    assert db_path.exists()

    from radar_core.db import get_engine
    from radar_core.models.audit import Audit, ToolResult

    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        audits = session.exec(select(Audit)).all()
        assert len(audits) == 1
        results = session.exec(select(ToolResult)).all()
        assert len(results) == 1
        assert results[0].tool_name == "example-git-log"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_cli.py -v`
Expected: FAIL — `radar_audit.cli` doesn't exist.

- [ ] **Step 3: Write the implementation**

`radar-audit/src/radar_audit/cli.py`:
```python
from __future__ import annotations

import os
from pathlib import Path

import typer
from radar_core.db import get_engine, get_session

from radar_audit.config import load_portfolio_config
from radar_audit.orchestrator import AuditPlan, execute_audit, plan_audit
from radar_audit.runner import ToolRunner
from radar_audit.runners.example import ExampleGitLogRunner

app = typer.Typer()

DEFAULT_PORTFOLIO_YAML = Path(__file__).resolve().parents[2] / "portfolio.yaml"
DEFAULT_RUNNERS: list[ToolRunner] = [ExampleGitLogRunner()]


class MissingDatabaseUrlError(RuntimeError):
    """Raised when RADAR_DATABASE_URL is not set for a real (non-dry-run) audit."""


def _database_url() -> str:
    url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        raise MissingDatabaseUrlError(
            "RADAR_DATABASE_URL must be set explicitly; radar-audit never assumes "
            "a default database location."
        )
    return url


@app.command()
def run(
    repo_name: str = typer.Argument(None, help="Repository name from portfolio.yaml"),
    all_repos: bool = typer.Option(False, "--all", help="Audit every repository in portfolio.yaml"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the audit plan without executing anything"),
    config_path: Path = typer.Option(DEFAULT_PORTFOLIO_YAML, "--config", help="Path to portfolio.yaml"),
) -> None:
    if not all_repos and repo_name is None:
        raise typer.BadParameter("Provide a repository name or use --all")

    config = load_portfolio_config(config_path)
    repo_names = config.repositories if all_repos else [repo_name]

    if dry_run:
        for name in repo_names:
            _print_plan(plan_audit(config, name))
        return

    engine = get_engine(_database_url())
    session = get_session(engine)
    try:
        for name in repo_names:
            execute_audit(session, config, name, DEFAULT_RUNNERS)
    finally:
        session.close()
        engine.dispose()


def _print_plan(plan: AuditPlan) -> None:
    typer.echo(f"Repository: {plan.repository_name} ({plan.repository_path})")
    typer.echo(f"Excluded worktrees: {[str(p) for p in plan.exclude_paths]}")
    for subproject in plan.subprojects:
        typer.echo(f"  subproject: {subproject.path} [{subproject.stack}]")
        for tool_runner in DEFAULT_RUNNERS:
            typer.echo(f"    would run: {tool_runner.tool_name}")


if __name__ == "__main__":
    app()
```

`radar-audit/README.md`:
```markdown
# radar-audit

Tool orchestration and normalization engine for Portfolio-Engineering-Radar.

## Prerequisites

`radar-audit` writes to the same SQLite database as `radar-core`'s Alembic
migrations. Before running a real (non-dry-run) audit for the first time,
apply the migrations against the target database:

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Usage

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-audit radar-audit run <repo-name>
    uv run --package radar-audit radar-audit run --all
    uv run --package radar-audit radar-audit run <repo-name> --dry-run

`--dry-run` prints the discovered sub-projects and the tools that would run,
without touching the database.

Repository scope and the local checkout root are configured in
`portfolio.yaml` (versioned in this directory).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_cli.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/cli.py radar-audit/README.md radar-audit/tests/test_cli.py
git commit -m "feat(radar-audit): add Typer CLI with run and --dry-run"
```

---

### Task 11: Full-suite verification and lint/type-check pass

**Files:** none created — this task verifies Tasks 1-10 together.

**Interfaces:** none new.

- [ ] **Step 1: Run the full radar-audit test suite**

Run: `cd radar-audit && uv run pytest -v`
Expected: PASS, all tests from Tasks 1-10 (approximately 42 tests total).

- [ ] **Step 2: Run ruff and ruff-format across both packages**

Run: `uv run ruff check radar-core radar-audit` (from repo root)
Run: `uv run ruff format --check radar-core radar-audit`
Expected: no findings. If `ruff format --check` reports unformatted files, run `uv run ruff format radar-core radar-audit` and re-check.

- [ ] **Step 3: Run mypy strict on radar-audit**

Run: `cd radar-audit && uv run mypy src/radar_audit`
Expected: no errors. If the `ToolRunner` `Protocol` or the `db_session`/`Session` typing surfaces an error, fix the annotation at its source (do not add `# type: ignore` without first trying an explicit type).

- [ ] **Step 4: Run the pre-commit hooks manually against the new files**

Run: `uv run pre-commit run --files $(git diff --name-only main... ; git diff --cached --name-only)` (or, more simply, `uv run pre-commit run --all-files`)
Expected: all hooks pass (ruff, ruff-format, mypy-radar-core, mypy-radar-audit).

- [ ] **Step 5: Manual dry-run smoke test against a real repo**

Run (from repo root):
```bash
uv run --package radar-audit radar-audit run Portfolio-Engineering-Radar --dry-run
```
Expected: prints `Portfolio-Engineering-Radar` as the repository, at least two sub-projects (root `python` from the workspace `pyproject.toml`, plus `radar-core` and `radar-audit` as first-level `python` sub-projects), and `would run: example-git-log` for each. No `radar.db` file is created by this command.

This step has no code to commit — it is a manual verification gate confirming the full increment 2.0 pipeline behaves as designed against a real (not fixture) repository. If it fails, return to the relevant earlier task and fix the underlying module; do not patch behavior only in this step.

---

## Self-Review Notes

- **Spec coverage:** every §-numbered element of the design spec has a task: package layout (Task 1), CLI (Task 10), 7-step orchestration flow (Tasks 4, 5, 8, 9), `portfolio.yaml` (Task 3), `ToolResult` storage decision (unchanged, no task needed — verified by Task 9's assertions using the existing `radar_core` model), execution/error-handling model (Task 9), discovery heuristic (Task 4), taxonomy encoding (Task 7), testing strategy (Task 2 infra, used throughout).
- **Ambiguity resolved during planning, not left open:** the spec didn't cover the `Audit` unique-index-on-clean-commit interaction with re-runs; Task 8 resolves it (reuse existing clean-commit `Audit`, always create a new row for dirty checkouts) and states the reasoning in a docstring. The spec also didn't specify which quality-framework.md catalog rows are cross-referenced-only (archetype `—`); Task 7 makes the exact two exclusions (10.3, 12.1) explicit with the source document's own justification quoted.
- **Type consistency checked:** `ToolRunner.run` signature (`subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput`) is identical in `runner.py` (Task 6), `runners/example.py` (Task 6), and every call site in `orchestrator.py` (Task 9). `PortfolioConfig` field names (`repos_root`, `repositories`) are identical between Task 3's definition and every later task that constructs or consumes it (Tasks 9, 10).
