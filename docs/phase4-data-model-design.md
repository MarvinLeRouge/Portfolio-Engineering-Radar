# Phase 4 — Data model design (`radar-core`)

Status: **approved**, ready for implementation planning.

Sub-project 1 of 4 in Phase 4 (see `TODO.md`), foundation for the other three (tool orchestration, dashboard, report generation). Refines the entity list first proposed in `docs/system-design.md#5`, applying the stack decisions from `docs/open-decisions.md` D5/D16.

## Context

`docs/system-design.md#5` proposed 13 entities at Phase 0, before any implementation-level detail existed. This spec resolves the implementation questions that proposal deliberately left open, and corrects one real ambiguity discovered during design: `Audit` originally bundled "capturing repo state" and "applying a methodology to score it" into a single entity referencing exactly one `MethodologyVersion`. That doesn't hold once re-scoring the same commit under a later methodology version is considered (see "Audit vs ScoringRun split" below).

## Package structure

```
Portfolio-Engineering-Radar/
  pyproject.toml            # root: declares the uv workspace
                             # [tool.uv.workspace] members = ["radar-core", "radar-audit", "radar-api"]
  radar-core/
    pyproject.toml          # declares the radar-core package (sqlmodel, alembic)
    src/radar_core/
      __init__.py
      models/
        __init__.py
        repository.py
        methodology.py      # MethodologyVersion, Category, Criterion
        audit.py            # Audit, ToolResult
        scoring.py          # ScoringRun, Score
        finding.py          # Finding, Evidence, Recommendation
        roadmap.py          # ImprovementTask, RoadmapItem
        snapshot.py
      db.py                 # engine/session factory, URL passed explicitly, never a global default
      enums.py               # all shared Python Enums
    alembic/
      env.py
      versions/
    alembic.ini
    tests/
      conftest.py            # db_session fixture (see Testing below)
      models/
        test_repository.py
        test_methodology.py
        test_audit.py
        test_scoring.py
        test_finding.py
        test_roadmap.py
        test_snapshot.py
      test_fixture_isolation.py
```

`radar-audit` and `radar-api` (added in later sub-projects) depend on `radar-core` as a workspace member (`{ workspace = true }`), never duplicating models. `radar-dashboard` (Vue/Vite/Node) stays outside this Python workspace, with its own `package.json`.

## Data model

Entity table, PK strategy = auto-increment integer everywhere (native SQLite `rowid` aliasing, no `AUTOINCREMENT` keyword needed — see decision log). All enum-valued fields use Python `Enum` + SQLAlchemy `Enum` type (`VARCHAR` + generated `CHECK` constraint).

| Entity | Key fields | Relations |
|---|---|---|
| `Repository` | `id`, `name`, `path`, `created_at` | 1—N `Audit` |
| `MethodologyVersion` | `id`, `version_label`, `frozen_at`, `notes` | 1—N `Category`, 1—N `ScoringRun` |
| `Category` | `id`, `methodology_version_id`, `name`, `weight`, `order` | belongs to `MethodologyVersion`, 1—N `Criterion` |
| `Criterion` | `id`, `category_id`, `name`, `description`, `weight`, `scoring_model` (`FIXED_SCALE`/`STATUS_4STATE`) | belongs to `Category`, 1—N `Finding`, 1—N `Score` |
| `Audit` | `id`, `repository_id`, `commit_sha`, `is_dirty` (bool), `audited_at`, `network_flags` (JSON, D6/D15) | belongs to `Repository`, 1—N `ToolResult`, 1—N `ScoringRun` |
| `ToolResult` | `id`, `audit_id`, `tool_name`, `tool_version`, `command`, `raw_output` (JSON), `exit_code`, `ran_at`, `duration_ms` | belongs to `Audit` |
| `ScoringRun` | `id`, `audit_id`, `methodology_version_id`, `scored_at`, `global_score`, `global_confidence` (enum) — unique `(audit_id, methodology_version_id)` | belongs to `Audit` + `MethodologyVersion`, 1—N `Finding`, 1—N `Score` |
| `Finding` | `id`, `scoring_run_id`, `criterion_id`, `tool_result_id` (nullable), `severity` (enum), `description`, `file`, `line`, `estimated_effort`, `confidence` (enum), `status` (enum), `human_verdict` (enum, D14), `detected_at` | belongs to `ScoringRun` + `Criterion`, 0—N `Evidence`, N—N `ImprovementTask` |
| `Evidence` | `id`, `finding_id` (nullable), `score_id` (nullable, exactly one non-null via `CHECK`), `evidence_type` (enum), `content`, `created_at` | belongs to `Finding` or `Score` |
| `Score` | `id`, `scoring_run_id`, `criterion_id` (nullable), `category_id` (nullable), `level` (`CRITERION`/`CATEGORY`/`GLOBAL`), `value`, `confidence` (enum), `na_reason` (nullable) | belongs to `ScoringRun` + `Criterion`/`Category`, 0—N `Evidence` |
| `Recommendation` | `id`, `finding_id`, `text`, `created_at` | belongs to `Finding` |
| `ImprovementTask` | `id`, `title`, `description`, `created_at` | N—N `Finding` (association table), 0—1 `RoadmapItem` |
| `RoadmapItem` | `id`, `improvement_task_id` (unique), `status` (enum), `priority`, `estimated_effort`, `estimated_impact`, `promoted_at`, `done_at`, `done_evidence_id` (FK `Evidence`, required for `DONE`) | optional 1—1 with `ImprovementTask` |
| `Snapshot` | `id`, `taken_at`, `portfolio_global_score`, `portfolio_global_confidence`, `details` (JSON, per-repo/category rollup) | materialized rollup, not tied to a single `Audit`/`ScoringRun` |

### Audit vs ScoringRun split

`Audit` = one capture of repo state (repo + commit + raw `ToolResult`s), independent of methodology — tools never re-run for the same clean commit. `ScoringRun` = applying one `MethodologyVersion` to one `Audit`, producing `Finding`/`Score`. An `Audit` can have several `ScoringRun`s over time.

- **Same commit, new methodology** → same `Audit`, new `ScoringRun`. Comparing methodologies = listing the `ScoringRun`s of that `Audit`.
- **Different commits** → different `Audit`s, each with its own `ScoringRun`(s). No transition to model; it's a normal timeline. The dashboard should flag on trend charts when `MethodologyVersion` changes between two points, so a score change isn't misread as a real regression.

`Snapshot` is a materialized portfolio-level rollup for the dashboard's trend view (repos are audited on different days, so a "portfolio score at time T" isn't a single query away) — not a source of truth.

### Identifying repo state

`Audit.commit_sha` + `Audit.is_dirty` (from `git status --porcelain`). A partial unique index `Audit(repository_id, commit_sha) WHERE is_dirty = 0` guarantees only one "clean" `Audit` per commit is reusable as a re-score base; dirty audits can accumulate freely since their `ToolResult`s are only valid for that exact instant and are never reused.

### ImprovementTask vs RoadmapItem split

`ImprovementTask` is born automatically during normalization (grouping `Finding`s into a unit of work). It only becomes a tracked `RoadmapItem` (status/priority/effort/impact) when explicitly promoted — matches Phase 6's two distinct steps ("convert findings into tasks" then "publish the living roadmap").

## Constraints, cascade, indices

- **Append-only**: `Audit`, `ToolResult`, `ScoringRun`, `Score`, `Evidence`, `Recommendation` are never updated after creation. `Finding` is append-only except `status`/`human_verdict` (D14, mutated only through the dashboard's narrow write API). `RoadmapItem` is the only entity with an evolving lifecycle.
- **`RoadmapItem.done_evidence_id` requirement**: "must be set when `status` transitions to `DONE`" is enforced at the application layer (same `human_confirmation` gate pattern as D11/D14), not as a DB `CHECK` — a conditional-on-status constraint isn't portably expressible in SQLite `CHECK`.
- **No cascade delete** exposed via the API. Repository removal from the portfolio (if it ever happens, D1) would be a separate, explicit admin operation — out of scope until actually needed.
- **Indices**: explicit `index=True` on all FK columns used in frequent filters (`repository_id`, `scoring_run_id`, `criterion_id`, `finding_id`) — SQLAlchemy does not index FKs automatically on SQLite. Partial unique index on `Audit(repository_id, commit_sha) WHERE is_dirty = 0` (see above).
- **Timestamps**: UTC-aware `datetime` everywhere (`datetime.now(timezone.utc)` as `default_factory`), never naive.

## Testing

- `alembic upgrade head` is part of the test suite's schema setup (not `SQLModel.metadata.create_all()`), so a migration regression is caught by tests, not discovered later.
- `db_session` fixture (function-scoped): builds a real temporary SQLite file per test via pytest's `tmp_path` (not `:memory:`, which doesn't survive across Alembic's and the test's separate connections), runs `alembic upgrade head` against that file's URL, opens a `Session` on it, yields it.
- `db.py`'s engine/session factory takes the database URL as an explicit required parameter — no implicit default read at import time, so production code structurally cannot fall back to `radar.db` by accident.
- The fixture itself asserts the bound engine URL points inside `tmp_path` and is never `radar.db`, before yielding to the test.
- `test_fixture_isolation.py` verifies two fixture instances produce distinct files, and that the expected tables exist in `sqlite_master` after the Alembic replay — proof the migration actually ran against that file.
- Test files mirror `src/radar_core/models/` structure. Coverage: entity creation, constraints (partial unique on `Audit`, `CHECK` on `Evidence`), relationship cascades (`Category`→`Criterion`, `Finding`→`Evidence`), and one end-to-end test covering `Audit` → `ScoringRun` → `Finding`/`Score` → `ImprovementTask` → `RoadmapItem`.

## Decision log

| # | Decision | Rationale |
|---|---|---|
| 1 | Shared `radar-core` package (uv workspace member) over duplicating models in `radar-audit`/`radar-api` | Avoids drift between orchestrator and API; `radar-audit` never depends on API code |
| 2 | Auto-increment integer PKs over UUID | SQLite has no native UUID generation (app-level only); local-first single-source project has no distributed/merge use case that would justify UUIDs |
| 3 | Python `Enum` + SQLAlchemy `Enum` type over free-form strings | DB-level `CHECK` constraint catches invalid values inserted outside the app code path |
| 4 | `Audit`/`ScoringRun` split over a single bundled entity | A single commit can be re-scored under multiple methodology versions; bundling made that unrepresentable without either mutating history or duplicating `ToolResult` |
| 5 | `Snapshot` as materialized rollup, not source of truth | Portfolio-level trend view needs an aggregate across repos audited on different days; full history already lives in `ScoringRun`/`Score` |
| 6 | `Audit.commit_sha` + `is_dirty` flag, partial unique index | A dirty working tree makes commit SHA alone insufficient to guarantee `ToolResult` reuse is safe |
| 7 | `ImprovementTask`/`RoadmapItem` as separate tables (optional 1—1) | Not every generated task is promoted to a tracked roadmap item; matches the two distinct Phase 6 steps |
| 8 | Tests replay Alembic migrations (temp file DB) rather than `create_all()` | Migrations are part of the shipped artifact; a regression there must fail tests |
| 9 | Root-level `pyproject.toml` declares the uv workspace, each package keeps its own | Standard `uv` workspace convention; lets `radar-audit`/`radar-api` reference `radar-core` without publishing to PyPI |
