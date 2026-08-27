# radar-core Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `radar-core`, the shared SQLModel data model and Alembic migrations for Portfolio-Engineering-Radar, as its own installable package inside a `uv` workspace.

**Architecture:** One Python package (`radar-core`) exposing 13 SQLModel table classes plus one association table across seven model modules, backed by SQLite via Alembic migrations. Tests replay the real migrations against a fresh temporary SQLite file per test (no `:memory:`, no `create_all()`), with an explicit isolation guard so tests can never touch the real `radar.db`.

**Tech Stack:** Python 3.12, `uv` (workspace + dependency management), SQLModel, Alembic, SQLite, pytest, ruff, mypy.

**Spec:** `docs/phase4-data-model-design.md` — this plan implements it in full; executors should read both.

## Global Constraints

- Auto-increment integer primary keys everywhere (no UUIDs) — spec decision log #2.
- All enum-valued fields use Python `Enum` + SQLAlchemy `Enum` type, never free-form strings — spec decision log #3.
- `Audit`/`ScoringRun` are separate entities, never merged — spec decision log #4.
- `Audit.commit_sha` + `Audit.is_dirty`, with a partial unique index `(repository_id, commit_sha) WHERE is_dirty = 0` — spec decision log #6.
- `ImprovementTask`/`RoadmapItem` are separate tables, optional 1—1 — spec decision log #7.
- Tests build schema via `alembic upgrade head` against a real temporary file per test, never `SQLModel.metadata.create_all()` — spec decision log #8.
- `db.py`'s engine/session factory takes the database URL as an explicit required parameter, never an implicit default — spec Testing section.
- Root `pyproject.toml` declares the `uv` workspace; each package keeps its own `pyproject.toml` — spec decision log #9.
- UTC-aware `datetime` everywhere (`datetime.now(timezone.utc)` as `default_factory`), never naive.
- Every SQLite-targeting Alembic migration must be batch-mode safe (`render_as_batch=True`), since SQLite cannot `ALTER TABLE` most changes directly.

---

### Task 0: Workspace and package scaffolding

**Files:**
- Create: `pyproject.toml` (repo root)
- Create: `radar-core/pyproject.toml`
- Create: `radar-core/src/radar_core/__init__.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: an importable, empty `radar_core` package, installed in the workspace venv.

- [ ] **Step 1: Create the root workspace `pyproject.toml`**

```toml
[tool.uv.workspace]
members = ["radar-core"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 2: Create `radar-core/pyproject.toml`**

```toml
[project]
name = "radar-core"
version = "0.1.0"
description = "Shared data model (SQLModel) and Alembic migrations for Portfolio-Engineering-Radar."
requires-python = ">=3.12"
dependencies = [
    "sqlmodel>=0.0.22",
    "alembic>=1.13",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "mypy>=1.11",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/radar_core"]
```

- [ ] **Step 3: Create the empty package**

```python
# radar-core/src/radar_core/__init__.py
```

(Empty file — just marks the package.)

- [ ] **Step 4: Update `.gitignore`**

Add these lines to the existing `.gitignore`:

```
.venv/
__pycache__/
*.db
.pytest_cache/
.mypy_cache/
```

(`.ruff_cache/` is already implicitly untracked at the root — verify it's covered; if not, add it too.)

- [ ] **Step 5: Sync the workspace and verify the package imports**

Run: `uv sync`
Expected: completes without error, creates `.venv/` and `uv.lock` at the repo root.

Run: `uv run --package radar-core python -c "import radar_core; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock radar-core/pyproject.toml radar-core/src/radar_core/__init__.py .gitignore
git commit -m "chore(radar-core): scaffold uv workspace and empty package"
```

---

### Task 1: Shared enums

**Files:**
- Create: `radar-core/src/radar_core/enums.py`
- Test: `radar-core/tests/test_enums.py`

**Interfaces:**
- Produces: `ScoringModel`, `ScoreLevel`, `Confidence`, `FindingSeverity`, `FindingStatus`, `HumanVerdict`, `EvidenceType`, `RoadmapStatus` — all `str, Enum` subclasses, consumed by every model task from Task 6 onward.

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/test_enums.py
from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    RoadmapStatus,
    ScoreLevel,
    ScoringModel,
)


def test_confidence_members():
    assert {c.value for c in Confidence} == {"HIGH", "MEDIUM", "LOW"}


def test_human_verdict_members():
    assert {v.value for v in HumanVerdict} == {
        "UNREVIEWED",
        "TRUE_POSITIVE",
        "FALSE_POSITIVE",
    }


def test_score_level_members():
    assert {level.value for level in ScoreLevel} == {"CRITERION", "CATEGORY", "GLOBAL"}


def test_scoring_model_members():
    assert {m.value for m in ScoringModel} == {"FIXED_SCALE", "STATUS_4STATE"}


def test_finding_severity_members():
    assert {s.value for s in FindingSeverity} == {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFO",
    }


def test_finding_status_members():
    assert {s.value for s in FindingStatus} == {"OPEN", "RESOLVED", "WONT_FIX"}


def test_evidence_type_members():
    assert {t.value for t in EvidenceType} == {
        "TOOL_OUTPUT_EXCERPT",
        "HUMAN_CONFIRMATION",
        "EXTERNAL_REFERENCE",
    }


def test_roadmap_status_members():
    assert {s.value for s in RoadmapStatus} == {"TODO", "IN_PROGRESS", "DONE", "WONT_FIX"}
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/test_enums.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.enums'`

- [ ] **Step 3: Implement**

```python
# radar-core/src/radar_core/enums.py
from enum import Enum


class ScoringModel(str, Enum):
    FIXED_SCALE = "FIXED_SCALE"
    STATUS_4STATE = "STATUS_4STATE"


class ScoreLevel(str, Enum):
    CRITERION = "CRITERION"
    CATEGORY = "CATEGORY"
    GLOBAL = "GLOBAL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WONT_FIX = "WONT_FIX"


class HumanVerdict(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceType(str, Enum):
    TOOL_OUTPUT_EXCERPT = "TOOL_OUTPUT_EXCERPT"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"


class RoadmapStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    WONT_FIX = "WONT_FIX"
```

- [ ] **Step 4: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/test_enums.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-core/src/radar_core/enums.py radar-core/tests/test_enums.py
git commit -m "feat(radar-core): add shared enums"
```

---

### Task 2: Database engine/session factory

**Files:**
- Create: `radar-core/src/radar_core/db.py`
- Test: `radar-core/tests/test_db.py`

**Interfaces:**
- Produces: `get_engine(database_url: str) -> Engine`, `get_session(engine: Engine) -> Session` — consumed by Task 4's `conftest.py` fixture and, later, by `radar-audit`/`radar-api`.

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/test_db.py
from radar_core.db import get_engine, get_session


def test_get_engine_binds_to_given_url(tmp_path):
    db_path = tmp_path / "engine_test.db"
    engine = get_engine(f"sqlite:///{db_path}")

    assert str(engine.url) == f"sqlite:///{db_path}"


def test_two_engines_on_different_urls_are_independent(tmp_path):
    engine_a = get_engine(f"sqlite:///{tmp_path / 'a.db'}")
    engine_b = get_engine(f"sqlite:///{tmp_path / 'b.db'}")

    assert engine_a.url != engine_b.url


def test_get_session_returns_open_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'session_test.db'}")

    session = get_session(engine)
    try:
        assert session.is_active
    finally:
        session.close()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.db'`

- [ ] **Step 3: Implement**

```python
# radar-core/src/radar_core/db.py
from sqlalchemy import Engine
from sqlmodel import Session, create_engine


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def get_session(engine: Engine) -> Session:
    return Session(engine)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/test_db.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-core/src/radar_core/db.py radar-core/tests/test_db.py
git commit -m "feat(radar-core): add explicit-url engine/session factory"
```

---

### Task 3: Alembic bootstrap

**Files:**
- Create: `radar-core/alembic.ini`
- Create: `radar-core/alembic/env.py`
- Create: `radar-core/alembic/script.py.mako`
- Create: `radar-core/src/radar_core/models/__init__.py` (empty for now — populated model-by-model from Task 5 onward)
- Create: `radar-core/alembic/versions/0001_initial_empty_schema.py` (generated)

**Interfaces:**
- Consumes: nothing yet (no models exist).
- Produces: a working `alembic upgrade head` against any SQLite file, driven by the `RADAR_DATABASE_URL` environment variable — consumed by Task 4's test fixture and every model task's migration step from here on.

- [ ] **Step 1: Create `radar-core/alembic.ini`**

```ini
[alembic]
script_location = %(here)s/alembic
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Note the deliberately blank `sqlalchemy.url` — `env.py` (below) refuses to fall back to any default and requires `RADAR_DATABASE_URL` to be set, so this file can never silently point at a real database.

- [ ] **Step 2: Create `radar-core/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Create `radar-core/alembic/env.py`**

```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from radar_core.models import *  # noqa: F401,F403 — registers all tables on SQLModel.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "RADAR_DATABASE_URL must be set explicitly; radar-core never assumes "
            "a default database location."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create the empty models package**

```python
# radar-core/src/radar_core/models/__init__.py
```

(Empty for now — Task 5 onward adds `from radar_core.models.X import ...` lines here as each model module is created.)

- [ ] **Step 5: Generate and verify the initial (empty) migration**

Run, from `radar-core/`:

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_bootstrap_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "initial empty schema"
```

Expected: creates `radar-core/alembic/versions/0001_initial_empty_schema.py` (filename will include a generated hex revision id) with empty `upgrade()`/`downgrade()` bodies (no models registered yet, so nothing to diff).

Then verify it applies cleanly:

```bash
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
sqlite3 "${RADAR_DATABASE_URL#sqlite:///}" ".tables"
```

Expected: `.tables` output shows `alembic_version` (and nothing else, since no models exist yet).

Unset the throwaway variable afterward: `unset RADAR_DATABASE_URL`.

- [ ] **Step 6: Commit**

```bash
git add radar-core/alembic.ini radar-core/alembic/env.py radar-core/alembic/script.py.mako radar-core/alembic/versions/ radar-core/src/radar_core/models/__init__.py
git commit -m "chore(radar-core): bootstrap alembic with explicit-url env.py"
```

---

### Task 4: Test fixture and isolation guard

**Files:**
- Create: `radar-core/tests/conftest.py`
- Test: `radar-core/tests/test_fixture_isolation.py`

**Interfaces:**
- Consumes: `get_engine` (Task 2), `RADAR_DATABASE_URL`-driven Alembic (Task 3).
- Produces: `db_session` pytest fixture, used by every model test from Task 5 onward.

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/test_fixture_isolation.py
from pathlib import Path

from sqlalchemy import inspect


def test_fixture_creates_file_inside_tmp_path(db_session, tmp_path):
    expected_path = tmp_path / "test.db"
    assert expected_path.exists()
    assert str(db_session.get_bind().url).startswith(f"sqlite:///{tmp_path}")


def test_fixture_never_points_at_production_db(db_session):
    assert Path(db_session.get_bind().url.database).name != "radar.db"


def test_migration_ran_against_the_fixture_file(db_session):
    inspector = inspect(db_session.get_bind())
    assert "alembic_version" in inspector.get_table_names()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/test_fixture_isolation.py -v`
Expected: FAIL with `fixture 'db_session' not found`

- [ ] **Step 3: Implement the fixture**

```python
# radar-core/tests/conftest.py
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlmodel import Session

from radar_core.db import get_engine

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = ALEMBIC_INI.parent / "alembic"


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        del os.environ["RADAR_DATABASE_URL"]


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    assert str(engine.url).startswith(f"sqlite:///{tmp_path}")
    assert Path(engine.url.database).name != "radar.db"

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

- [ ] **Step 4: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/test_fixture_isolation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add radar-core/tests/conftest.py radar-core/tests/test_fixture_isolation.py
git commit -m "test(radar-core): add migration-backed db_session fixture with isolation guard"
```

---

### Task 5: `Repository` model

**Files:**
- Create: `radar-core/src/radar_core/models/repository.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_repository.py`

**Interfaces:**
- Produces: `Repository` (fields: `id`, `name`, `path`, `created_at`) — consumed by Task 7 (`Audit.repository_id`).

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_repository.py
from datetime import UTC

from radar_core.models.repository import Repository


def test_create_repository(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    assert repo.id is not None
    assert repo.created_at.tzinfo is not None
    assert repo.created_at.tzinfo == UTC


def test_repository_path_must_be_unique(db_session):
    db_session.add(Repository(name="A", path="/same/path"))
    db_session.commit()

    db_session.add(Repository(name="B", path="/same/path"))
    with __import__("pytest").raises(Exception):
        db_session.commit()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.repository'`

- [ ] **Step 3: Implement the model**

```python
# radar-core/src/radar_core/models/repository.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Repository(SQLModel, table=True):
    __tablename__ = "repository"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    path: str = Field(unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.repository import Repository

__all__ = ["Repository"]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_repo_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add repository table"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

Expected: new file under `radar-core/alembic/versions/` creating the `repository` table (columns `id`, `name`, `path`, `created_at`, unique constraint on `path`), applies without error.

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/repository.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_repository.py
git commit -m "feat(radar-core): add Repository model"
```

---

### Task 6: `MethodologyVersion`, `Category`, `Criterion` models

**Files:**
- Create: `radar-core/src/radar_core/models/methodology.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_methodology.py`

**Interfaces:**
- Consumes: `ScoringModel` (Task 1).
- Produces: `MethodologyVersion`, `Category`, `Criterion` — consumed by Task 8 (`ScoringRun.methodology_version_id`, `Score.category_id`/`criterion_id`) and Task 9 (`Finding.criterion_id`).

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_methodology.py
from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion


def test_create_methodology_with_category_and_criterion(db_session):
    version = MethodologyVersion(version_label="1.0", notes="Frozen 2026-08-26")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(
        methodology_version_id=version.id, name="Security", weight=1.5, order=4
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks, git-history mode",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    assert criterion.id is not None
    assert criterion.category_id == category.id
    assert category.methodology_version_id == version.id


def test_methodology_version_label_must_be_unique(db_session):
    db_session.add(MethodologyVersion(version_label="1.0"))
    db_session.commit()

    db_session.add(MethodologyVersion(version_label="1.0"))
    with __import__("pytest").raises(Exception):
        db_session.commit()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_methodology.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.methodology'`

- [ ] **Step 3: Implement the models**

```python
# radar-core/src/radar_core/models/methodology.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import ScoringModel


class MethodologyVersion(SQLModel, table=True):
    __tablename__ = "methodology_version"

    id: int | None = Field(default=None, primary_key=True)
    version_label: str = Field(unique=True, index=True)
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: int | None = Field(default=None, primary_key=True)
    methodology_version_id: int = Field(foreign_key="methodology_version.id", index=True)
    name: str
    weight: float
    order: int


class Criterion(SQLModel, table=True):
    __tablename__ = "criterion"

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    name: str
    description: str
    weight: float
    scoring_model: ScoringModel = Field(sa_column=Column(SAEnum(ScoringModel), nullable=False))
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository

__all__ = ["Category", "Criterion", "MethodologyVersion", "Repository"]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_methodology_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add methodology_version, category, criterion tables"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

Note: `upgrade head` is run once *before* autogenerate too, since autogenerate diffs against a DB that already has the `repository` table's migration applied — running against a completely empty file would make it try to re-create `repository` as well.

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_methodology.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/methodology.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_methodology.py
git commit -m "feat(radar-core): add MethodologyVersion, Category, Criterion models"
```

---

### Task 7: `Audit`, `ToolResult` models

**Files:**
- Create: `radar-core/src/radar_core/models/audit.py`
- Modify: `radar-core/src/radar_core/models/repository.py` (add back-populated `audits` relationship)
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_audit.py`

**Interfaces:**
- Consumes: `Repository` (Task 5).
- Produces: `Audit` (fields: `id`, `repository_id`, `commit_sha`, `is_dirty`, `audited_at`, `network_flags`), `ToolResult` — consumed by Task 8 (`ScoringRun.audit_id`) and Task 9 (`Finding.tool_result_id`).

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_audit.py
import pytest
from sqlalchemy.exc import IntegrityError

from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository


def _make_repository(db_session) -> Repository:
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def test_create_audit_with_tool_result(db_session):
    repo = _make_repository(db_session)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    tool_result = ToolResult(
        audit_id=audit.id,
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
    assert tool_result.raw_output == {"findings": []}


def test_second_clean_audit_on_same_commit_is_rejected(db_session):
    repo = _make_repository(db_session)

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False))
    db_session.commit()

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_dirty_audits_on_same_commit_are_allowed(db_session):
    repo = _make_repository(db_session)

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=True))
    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=True))
    db_session.commit()  # must not raise
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.audit'`

- [ ] **Step 3: Implement the models**

```python
# radar-core/src/radar_core/models/audit.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, SQLModel


class Audit(SQLModel, table=True):
    __tablename__ = "audit"
    __table_args__ = (
        Index(
            "ix_audit_repo_commit_clean",
            "repository_id",
            "commit_sha",
            unique=True,
            sqlite_where=text("is_dirty = 0"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    repository_id: int = Field(foreign_key="repository.id", index=True)
    commit_sha: str = Field(index=True)
    is_dirty: bool = False
    audited_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    network_flags: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ToolResult(SQLModel, table=True):
    __tablename__ = "tool_result"

    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(foreign_key="audit.id", index=True)
    tool_name: str = Field(index=True)
    tool_version: str
    command: str
    raw_output: dict = Field(sa_column=Column(JSON))
    exit_code: int
    ran_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int
```

Note: the SQLite partial unique index (`sqlite_where`) is what makes `is_dirty=True` audits exempt from the "one clean audit per commit" rule — verified explicitly by `test_multiple_dirty_audits_on_same_commit_are_allowed` above.

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository

__all__ = ["Audit", "Category", "Criterion", "MethodologyVersion", "Repository", "ToolResult"]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_audit_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add audit, tool_result tables"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

Inspect the generated migration file: confirm the partial unique index is included with its `sqlite_where` clause — Alembic's autogenerate does pick up dialect-specific `Index` kwargs, but verify manually since this is the plan's single most failure-prone step. If the `sqlite_where` clause is missing from the generated `op.create_index(...)` call, add it by hand: `sqlite_where=sa.text("is_dirty = 0")`.

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_audit.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/audit.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_audit.py
git commit -m "feat(radar-core): add Audit, ToolResult models with clean-commit uniqueness"
```

---

### Task 8: `ScoringRun`, `Score` models

**Files:**
- Create: `radar-core/src/radar_core/models/scoring.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_scoring.py`

**Interfaces:**
- Consumes: `Audit` (Task 7), `MethodologyVersion`/`Category`/`Criterion` (Task 6), `Confidence`/`ScoreLevel` (Task 1).
- Produces: `ScoringRun`, `Score` — consumed by Task 9 (`Finding.scoring_run_id`, `Evidence.score_id`).

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_scoring.py
import pytest
from sqlalchemy.exc import IntegrityError

from radar_core.enums import Confidence, ScoreLevel, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun


def _make_audit_and_methodology(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    return audit, version, category, criterion


def test_create_scoring_run_with_scores(db_session):
    audit, version, category, criterion = _make_audit_and_methodology(db_session)

    scoring_run = ScoringRun(
        audit_id=audit.id, methodology_version_id=version.id, global_score=7.5,
        global_confidence=Confidence.HIGH,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    criterion_score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=10.0,
        confidence=Confidence.HIGH,
    )
    category_score = Score(
        scoring_run_id=scoring_run.id,
        category_id=category.id,
        level=ScoreLevel.CATEGORY,
        value=10.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(criterion_score)
    db_session.add(category_score)
    db_session.commit()

    assert scoring_run.id is not None
    assert criterion_score.criterion_id == criterion.id
    assert category_score.category_id == category.id


def test_scoring_run_unique_per_audit_and_methodology(db_session):
    audit, version, _category, _criterion = _make_audit_and_methodology(db_session)

    db_session.add(ScoringRun(audit_id=audit.id, methodology_version_id=version.id))
    db_session.commit()

    db_session.add(ScoringRun(audit_id=audit.id, methodology_version_id=version.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.scoring'`

- [ ] **Step 3: Implement the models**

```python
# radar-core/src/radar_core/models/scoring.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence, ScoreLevel


class ScoringRun(SQLModel, table=True):
    __tablename__ = "scoring_run"
    __table_args__ = (
        UniqueConstraint(
            "audit_id", "methodology_version_id", name="uq_scoringrun_audit_methodology"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(foreign_key="audit.id", index=True)
    methodology_version_id: int = Field(foreign_key="methodology_version.id", index=True)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    global_score: float | None = None
    global_confidence: Confidence | None = Field(
        default=None, sa_column=Column(SAEnum(Confidence), nullable=True)
    )


class Score(SQLModel, table=True):
    __tablename__ = "score"

    id: int | None = Field(default=None, primary_key=True)
    scoring_run_id: int = Field(foreign_key="scoring_run.id", index=True)
    criterion_id: int | None = Field(default=None, foreign_key="criterion.id", index=True)
    category_id: int | None = Field(default=None, foreign_key="category.id", index=True)
    level: ScoreLevel = Field(sa_column=Column(SAEnum(ScoreLevel), nullable=False))
    value: float
    confidence: Confidence = Field(sa_column=Column(SAEnum(Confidence), nullable=False))
    na_reason: str | None = None
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun

__all__ = [
    "Audit",
    "Category",
    "Criterion",
    "MethodologyVersion",
    "Repository",
    "Score",
    "ScoringRun",
    "ToolResult",
]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_scoring_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add scoring_run, score tables"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_scoring.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/scoring.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_scoring.py
git commit -m "feat(radar-core): add ScoringRun, Score models"
```

---

### Task 9: `Finding`, `Evidence`, `Recommendation` models

**Files:**
- Create: `radar-core/src/radar_core/models/finding.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_finding.py`

**Interfaces:**
- Consumes: `ScoringRun`/`Score` (Task 8), `Criterion` (Task 6), `ToolResult` (Task 7), `FindingSeverity`/`FindingStatus`/`HumanVerdict`/`Confidence`/`EvidenceType` (Task 1).
- Produces: `Finding`, `Evidence`, `Recommendation` — `Finding.id` consumed by Task 10 (`FindingImprovementTaskLink`).

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_finding.py
import pytest
from sqlalchemy.exc import IntegrityError

from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    return scoring_run, criterion


def test_create_finding_with_evidence_and_recommendation(db_session):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret in git history",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    assert finding.status == FindingStatus.OPEN
    assert finding.human_verdict == HumanVerdict.UNREVIEWED

    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.TOOL_OUTPUT_EXCERPT,
        content="gitleaks: generic-api-key at config.py:42",
    )
    recommendation = Recommendation(
        finding_id=finding.id, text="Rotate the credential and purge it from history."
    )
    db_session.add(evidence)
    db_session.add(recommendation)
    db_session.commit()

    assert evidence.score_id is None
    assert recommendation.finding_id == finding.id


def test_evidence_requires_exactly_one_parent(db_session):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="minor",
        confidence=Confidence.LOW,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    db_session.add(
        Evidence(
            finding_id=finding.id,
            score_id=None,
            evidence_type=EvidenceType.HUMAN_CONFIRMATION,
            content="ok",
        )
    )
    db_session.commit()  # exactly one parent set — must succeed

    db_session.add(
        Evidence(
            finding_id=None,
            score_id=None,
            evidence_type=EvidenceType.HUMAN_CONFIRMATION,
            content="orphan",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_finding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.finding'`

- [ ] **Step 3: Implement the models**

```python
# radar-core/src/radar_core/models/finding.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence, EvidenceType, FindingSeverity, FindingStatus, HumanVerdict


class Finding(SQLModel, table=True):
    __tablename__ = "finding"

    id: int | None = Field(default=None, primary_key=True)
    scoring_run_id: int = Field(foreign_key="scoring_run.id", index=True)
    criterion_id: int = Field(foreign_key="criterion.id", index=True)
    tool_result_id: int | None = Field(default=None, foreign_key="tool_result.id", index=True)
    severity: FindingSeverity = Field(sa_column=Column(SAEnum(FindingSeverity), nullable=False))
    description: str
    file: str | None = None
    line: int | None = None
    estimated_effort: str | None = None
    confidence: Confidence = Field(sa_column=Column(SAEnum(Confidence), nullable=False))
    status: FindingStatus = Field(
        default=FindingStatus.OPEN, sa_column=Column(SAEnum(FindingStatus), nullable=False)
    )
    human_verdict: HumanVerdict = Field(
        default=HumanVerdict.UNREVIEWED, sa_column=Column(SAEnum(HumanVerdict), nullable=False)
    )
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Evidence(SQLModel, table=True):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "(finding_id IS NOT NULL) + (score_id IS NOT NULL) = 1",
            name="ck_evidence_exactly_one_parent",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int | None = Field(default=None, foreign_key="finding.id", index=True)
    score_id: int | None = Field(default=None, foreign_key="score.id", index=True)
    evidence_type: EvidenceType = Field(sa_column=Column(SAEnum(EvidenceType), nullable=False))
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Recommendation(SQLModel, table=True):
    __tablename__ = "recommendation"

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id", index=True)
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun

__all__ = [
    "Audit",
    "Category",
    "Criterion",
    "Evidence",
    "Finding",
    "MethodologyVersion",
    "Recommendation",
    "Repository",
    "Score",
    "ScoringRun",
    "ToolResult",
]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_finding_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add finding, evidence, recommendation tables"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

Inspect the generated migration: confirm the `CheckConstraint` on `evidence` is included in `op.create_table(...)`. Alembic autogenerate does not always detect `CHECK` constraints depending on version — if missing, add `sa.CheckConstraint("(finding_id IS NOT NULL) + (score_id IS NOT NULL) = 1", name="ck_evidence_exactly_one_parent")` to the table's constraint list by hand.

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_finding.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/finding.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_finding.py
git commit -m "feat(radar-core): add Finding, Evidence, Recommendation models"
```

---

### Task 10: `ImprovementTask`, `RoadmapItem` models and the `Finding` N—N link

**Files:**
- Create: `radar-core/src/radar_core/models/links.py`
- Create: `radar-core/src/radar_core/models/roadmap.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_roadmap.py`

**Interfaces:**
- Consumes: `Finding` (Task 9), `Evidence` (Task 9), `RoadmapStatus` (Task 1).
- Produces: `FindingImprovementTaskLink`, `ImprovementTask`, `RoadmapItem`.

Note: `links.py` is one file more than the original design doc's file list — it holds only the `Finding`⟷`ImprovementTask` association table, kept separate to avoid a circular import between `finding.py` and `roadmap.py` (both would otherwise need to import each other's concrete class to build the `link_model=` relationship). Consistent with the design's intent, not a deviation from it.

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_roadmap.py
from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    RoadmapStatus,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun


def _make_finding(db_session) -> Finding:
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_improvement_task_links_to_finding_via_association_table(db_session):
    finding = _make_finding(db_session)

    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    link = db_session.get(FindingImprovementTaskLink, (finding.id, task.id))
    assert link is not None


def test_improvement_task_is_not_a_roadmap_item_until_promoted(db_session):
    finding = _make_finding(db_session)
    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    from sqlmodel import select

    assert db_session.exec(
        select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
    ).first() is None


def test_roadmap_item_promotion_with_done_evidence(db_session):
    finding = _make_finding(db_session)
    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=RoadmapStatus.TODO, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)

    done_evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.HUMAN_CONFIRMATION,
        content="Credential rotated and purged, confirmed by developer.",
    )
    db_session.add(done_evidence)
    db_session.commit()
    db_session.refresh(done_evidence)

    roadmap_item.status = RoadmapStatus.DONE
    roadmap_item.done_evidence_id = done_evidence.id
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)

    assert roadmap_item.status == RoadmapStatus.DONE
    assert roadmap_item.done_evidence_id == done_evidence.id
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_roadmap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.links'`

- [ ] **Step 3: Implement the models**

```python
# radar-core/src/radar_core/models/links.py
from __future__ import annotations

from sqlmodel import Field, SQLModel


class FindingImprovementTaskLink(SQLModel, table=True):
    __tablename__ = "finding_improvement_task_link"

    finding_id: int = Field(foreign_key="finding.id", primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", primary_key=True)
```

```python
# radar-core/src/radar_core/models/roadmap.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import RoadmapStatus


class ImprovementTask(SQLModel, table=True):
    __tablename__ = "improvement_task"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoadmapItem(SQLModel, table=True):
    __tablename__ = "roadmap_item"

    id: int | None = Field(default=None, primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", unique=True, index=True)
    status: RoadmapStatus = Field(
        default=RoadmapStatus.TODO, sa_column=Column(SAEnum(RoadmapStatus), nullable=False)
    )
    priority: int
    estimated_effort: str | None = None
    estimated_impact: str | None = None
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    done_at: datetime | None = None
    done_evidence_id: int | None = Field(default=None, foreign_key="evidence.id")
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import Score, ScoringRun

__all__ = [
    "Audit",
    "Category",
    "Criterion",
    "Evidence",
    "Finding",
    "FindingImprovementTaskLink",
    "ImprovementTask",
    "MethodologyVersion",
    "Recommendation",
    "Repository",
    "RoadmapItem",
    "Score",
    "ScoringRun",
    "ToolResult",
]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_roadmap_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add improvement_task, roadmap_item, finding_improvement_task_link tables"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_roadmap.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/links.py radar-core/src/radar_core/models/roadmap.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_roadmap.py
git commit -m "feat(radar-core): add ImprovementTask, RoadmapItem models and Finding link table"
```

---

### Task 11: `Snapshot` model

**Files:**
- Create: `radar-core/src/radar_core/models/snapshot.py`
- Modify: `radar-core/src/radar_core/models/__init__.py`
- Test: `radar-core/tests/models/test_snapshot.py`

**Interfaces:**
- Consumes: `Confidence` (Task 1).
- Produces: `Snapshot` — standalone, no FK dependents.

- [ ] **Step 1: Write failing test**

```python
# radar-core/tests/models/test_snapshot.py
from radar_core.enums import Confidence
from radar_core.models.snapshot import Snapshot


def test_create_snapshot(db_session):
    snapshot = Snapshot(
        portfolio_global_score=7.8,
        portfolio_global_confidence=Confidence.MEDIUM,
        details={"repositories": [{"name": "GeoChallenge-Tracker", "score": 8.1}]},
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.details["repositories"][0]["name"] == "GeoChallenge-Tracker"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_snapshot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_core.models.snapshot'`

- [ ] **Step 3: Implement the model**

```python
# radar-core/src/radar_core/models/snapshot.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence


class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshot"

    id: int | None = Field(default=None, primary_key=True)
    taken_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    portfolio_global_score: float
    portfolio_global_confidence: Confidence = Field(
        sa_column=Column(SAEnum(Confidence), nullable=False)
    )
    details: dict = Field(sa_column=Column(JSON))
```

Register it:

```python
# radar-core/src/radar_core/models/__init__.py
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import Score, ScoringRun
from radar_core.models.snapshot import Snapshot

__all__ = [
    "Audit",
    "Category",
    "Criterion",
    "Evidence",
    "Finding",
    "FindingImprovementTaskLink",
    "ImprovementTask",
    "MethodologyVersion",
    "Recommendation",
    "Repository",
    "RoadmapItem",
    "Score",
    "ScoringRun",
    "Snapshot",
    "ToolResult",
]
```

- [ ] **Step 4: Generate and apply the migration**

```bash
export RADAR_DATABASE_URL="sqlite:///$(mktemp -u /tmp/radar_snapshot_XXXX.db)"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "add snapshot table"
uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head
unset RADAR_DATABASE_URL
```

- [ ] **Step 5: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/models/test_snapshot.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Commit**

```bash
git add radar-core/src/radar_core/models/snapshot.py radar-core/src/radar_core/models/__init__.py radar-core/alembic/versions/ radar-core/tests/models/test_snapshot.py
git commit -m "feat(radar-core): add Snapshot model"
```

---

### Task 12: End-to-end integration test

**Files:**
- Test: `radar-core/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: every model from Tasks 5-11.
- Produces: nothing new — this is a pure verification task confirming the full chain works together, per the design spec's testing section.

- [ ] **Step 1: Write the test**

```python
# radar-core/tests/test_end_to_end.py
from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    RoadmapStatus,
    ScoreLevel,
    ScoringModel,
)
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import Score, ScoringRun


def test_full_audit_to_roadmap_chain(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="deadbeef", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="gitleaks",
        tool_version="8.18.0",
        command="gitleaks detect --report-format json",
        raw_output={"findings": [{"rule": "generic-api-key", "file": "config.py", "line": 42}]},
        exit_code=1,
        duration_ms=380,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks, git-history mode",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=version.id,
        global_score=2.0,
        global_confidence=Confidence.HIGH,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        tool_result_id=tool_result.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret in config.py",
        file="config.py",
        line=42,
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.TOOL_OUTPUT_EXCERPT,
        content="gitleaks: generic-api-key at config.py:42",
    )
    recommendation = Recommendation(
        finding_id=finding.id, text="Rotate the credential and purge it from history."
    )
    criterion_score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(evidence)
    db_session.add(recommendation)
    db_session.add(criterion_score)
    db_session.commit()

    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=RoadmapStatus.TODO, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)

    done_evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.HUMAN_CONFIRMATION,
        content="Credential rotated and purged, confirmed by developer.",
    )
    db_session.add(done_evidence)
    db_session.commit()
    db_session.refresh(done_evidence)

    roadmap_item.status = RoadmapStatus.DONE
    roadmap_item.done_evidence_id = done_evidence.id
    db_session.add(roadmap_item)
    db_session.commit()

    assert roadmap_item.status == RoadmapStatus.DONE
    assert roadmap_item.done_evidence_id == done_evidence.id
    assert finding.tool_result_id == tool_result.id
```

- [ ] **Step 2: Run test, verify it passes**

Run: `uv run --package radar-core pytest radar-core/tests/test_end_to_end.py -v`
Expected: PASS (1 test) — this exercises every table created across Tasks 5-11, so a failure here means an earlier task's model or migration has a real integration bug, not just an isolated unit issue.

- [ ] **Step 3: Run the full suite once**

Run: `uv run --package radar-core pytest radar-core/tests/ -v`
Expected: all tests across every task pass together.

- [ ] **Step 4: Commit**

```bash
git add radar-core/tests/test_end_to_end.py
git commit -m "test(radar-core): add end-to-end audit-to-roadmap integration test"
```

---

### Task 13: Pre-commit quality gate for `radar-core`

**Files:**
- Create: `.pre-commit-config.yaml` (repo root)

**Interfaces:**
- Produces: a working `pre-commit` config covering `radar-core`'s lint/format/type-check — dogfoods D12, the same criterion the audit system itself measures on target repos.

- [ ] **Step 1: Create the config**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
        files: ^radar-core/
      - id: ruff-format
        files: ^radar-core/
  - repo: local
    hooks:
      - id: mypy-radar-core
        name: mypy (radar-core)
        entry: uv run --package radar-core mypy src/radar_core
        language: system
        files: ^radar-core/src/
        pass_filenames: false
```

- [ ] **Step 2: Install and run the hooks**

Run: `uv tool install pre-commit` (if not already available), then:

```bash
pre-commit install
pre-commit run --all-files
```

Expected: `ruff`, `ruff-format` pass clean (or auto-fix and require a re-run). `mypy` may surface real type errors on first run — fix them in `radar-core/src/radar_core/` (not by loosening `[tool.mypy]` in the root `pyproject.toml`) until the hook passes clean.

- [ ] **Step 3: Verify tests still pass after any mypy-driven fixes**

Run: `uv run --package radar-core pytest radar-core/tests/ -v`
Expected: all tests still pass.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore(radar-core): add pre-commit lint/format/type-check gate"
```

(If Step 2 required source fixes to satisfy mypy, commit those as a separate preceding commit, e.g. `git commit -m "fix(radar-core): satisfy mypy strict mode"`, before the config commit — keeps the history honest about what changed why.)
