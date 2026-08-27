# radar-audit — Core Orchestration Engine (Increment 2.0) — Design

> Status: approved design, not yet implemented.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on `radar-core` (sub-project 1/4, merged to `main`).
> Spec references: `docs/system-design.md` (sections 3-4, 11-12), `docs/open-decisions.md` (D1, D6, D7, D15, D16), `docs/toolchain.md`, `docs/quality-framework.md`.

---

## 1. Scope decomposition

`radar-audit` (tool orchestration + normalization of raw results, per `docs/system-design.md`§4) is too large for a single implementation plan: `docs/quality-framework.md` defines ~50 criteria across 15 taxonomy categories, each with its own evidence/tool mapping, scoring archetype, and confidence rules.

**Decided decomposition:**

- **Increment 2.0 (this design)** — the core orchestration engine: repo/sub-project discovery, a generic tool-execution abstraction, worktree exclusion, raw `ToolResult` persistence, `Audit` creation, and taxonomy seeding. No category-specific tool integration or normalization.
- **Increments 2.1 through 2.15** — one per taxonomy category, in the catalog's numeric order (1. Architecture & design, 2. Code quality, ... 15. Technical debt). Each increment adds the concrete `ToolRunner`(s) for that category's criteria (per `docs/toolchain.md`'s validated + candidate tools, full catalog — not restricted to already-validated tools) **and** the corresponding normalization (raw → `Finding`/`Score`, archetype-appropriate, confidence-tagged). Each is its own spec → plan → implementation cycle, kept small enough to fit a session.

This document covers **increment 2.0 only**.

---

## 2. Goal

Stand up a working, tested pipeline — discover a repository, run a tool, persist the raw result, tie it to an `Audit` — with zero category-specific logic, so every later category increment builds on proven infrastructure instead of re-solving orchestration mechanics.

## 3. Architecture

```
radar-audit (new uv workspace member, depends on radar-core)
├── portfolio.yaml                        # versioned config: repos_root + in-scope repo list
├── src/radar_audit/
│   ├── cli.py                            # Typer app: `radar-audit run <repo>|--all [--dry-run]`
│   ├── config.py                         # load/validate portfolio.yaml
│   ├── discovery.py                      # repo + sub-project discovery (first-level manifests)
│   ├── worktree.py                       # worktree exclusion (git worktree list --porcelain)
│   ├── runner.py                         # ToolRunner interface + ephemeral execution
│   ├── runners/
│   │   └── example.py                    # throwaway ToolRunner (git log -1), end-to-end proof
│   ├── taxonomy/
│   │   ├── quality_framework_v1_0.yaml   # full catalog: 15 categories, ~50 criteria
│   │   └── seed.py                       # idempotent MethodologyVersion/Category/Criterion seed
│   └── orchestrator.py                   # discovery → runners → ToolResult → Audit
└── tests/
    ├── fixtures/                          # git repos created on the fly (pytest tmp_path)
    └── ...
```

`radar-audit` is added as a new member of the root `pyproject.toml` uv workspace (`[tool.uv.workspace] members = ["radar-core", "radar-audit"]`), depending on `radar-core` for models, `db.py`, and `types.py` — consistent with D16's monorepo decision. It uses `radar_core`'s existing engine/session helpers (`get_engine`, `get_session`) directly; no separate DB access layer.

## 4. CLI

Typer-based (`radar-audit run ...`), chosen for type-hint-driven ergonomics consistent with the SQLModel/Pydantic style already used in `radar-core`, and clean `--help`/sub-command generation.

```
radar-audit run <repo-name>       # audit one repo from portfolio.yaml
radar-audit run --all             # audit every repo in portfolio.yaml
radar-audit run <repo-name> --dry-run   # print what would run, execute nothing, write nothing
```

`--dry-run` performs discovery (repo resolution, sub-project detection, exclusion list) and prints a summary (repo, detected sub-projects/stacks, tools that would run) without executing any tool or writing to the database.

## 5. Config file — `portfolio.yaml`

Versioned in `radar-audit/` (not gitignored — unlike `radar.db`, it holds only configuration, no audit data). `repos_root` is defined exactly once, in this file — no environment-variable override.

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

This is the authoritative source for `--all`, and validates that a `<repo-name>` argument passed to `run` is actually in scope (per D1's confirmed portfolio list).

## 6. Repo & sub-project discovery

A repo's sub-projects are detected by **first-level manifest presence**: `pyproject.toml`/`requirements.txt` (Python), `package.json` (JS/TS), `composer.json` (PHP) — checked at the repo root and in each direct child directory. Each manifest found (root or one level down) defines one sub-project with its own stack. A repo with no sub-directory manifests is treated as a single sub-project (root = its own stack).

This covers the monorepo case (HexaRot, HiveMind: `backend/`, `frontend/`) without deeper recursion. `Portfolio-Engineering-Radar` itself will now be detected as Python (root `pyproject.toml` + `radar-core/pyproject.toml` as a second-level manifest — no longer a zero-marker repo as it was at Phase 0 inventory time).

## 7. Worktree exclusion

Per the orchestration rule generalized in `docs/toolchain.md` ("Containers" section, 2026-08-27): before invoking any tool, run `git worktree list --porcelain` against the target repo, extract every worktree path except the main one, and compute an exclusion list. This list is threaded through to whichever exclusion mechanism the specific `ToolRunner` supports (implemented per-runner in category increments; 2.0 only computes and exposes the list via `worktree.py`, it does not yet feed it to a real tool since none exist yet).

## 8. `ToolRunner` abstraction

A generic interface any tool integration implements:

```python
class ToolRunner(Protocol):
    tool_name: str
    tool_version: str

    def run(self, subproject_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        ...
```

`RawToolOutput` carries `command: str`, `raw_output: dict[str, Any]`, `exit_code: int`, `duration_ms: int` — the exact fields `radar_core.models.audit.ToolResult` already has. The orchestrator calls each registered runner, wraps failures (non-zero exit, timeout, crash) into a still-persisted `ToolResult` (see §10), and never aborts the whole audit on a single tool's failure.

**2.0's only registered runner** is a throwaway example (`git log -1 --format=%H`) — deterministic, fast, needs nothing beyond `git` itself — used purely to prove the pipeline end-to-end. It is explicitly disposable: increment 2.1 replaces/removes it as real runners land.

## 9. Taxonomy seeding

`docs/quality-framework.md`'s full catalog (15 categories, ~50 criteria, weights, scoring archetypes) is encoded as versioned data in `radar-audit/src/radar_audit/taxonomy/quality_framework_v1_0.yaml`, seeded in full by increment 2.0 — even for criteria whose `ToolRunner`/normalizer doesn't exist yet. Rationale: the taxonomy is frozen, versioned data (`docs/quality-framework.md` itself is frozen), not code logic tied to what's implemented; seeding it once avoids a `MethodologyVersion` that grows incrementally, which would complicate the versioning/comparability rules in `system-design.md`§9.

**Weight convention:** weights are expressed on a base-100 scale (e.g. `10.0` for Security, `6.15` for an equal-split category), not as fractions (`0.10`), for human readability. Aggregation math is unaffected — weighted averages use relative weights regardless of whether they sum to 100 or 1. This convention is binding for every category increment (2.1-2.15) that adds or adjusts criteria.

**`scoring_model` mapping:** the YAML's `scoring_model` field maps directly onto `radar_core.enums.ScoringModel` — `FIXED_SCALE` for archetype A (Anchored) and archetype B (Coverage), both 0-10 numeric scales; `STATUS_4STATE` for archetype C (Adoption). The A-vs-B distinction (fixed anchor conditions vs. a computed `covered/applicable` formula) is normalization logic owned by category increments, not represented in the structural data model.

Example excerpt:

```yaml
version_label: "Quality Framework v1.0"
notes: "Frozen 2026-08-26, see docs/quality-framework.md"
categories:
  - name: "Architecture & design"
    order: 1
    weight: 6.15
    criteria:
      - name: "Dependency direction / circularity"
        description: "dependency-cruiser (JS/TS), pydeps (Python) — cycle count"
        scoring_model: FIXED_SCALE
  - name: "Security"
    order: 4
    weight: 10.0
    criteria:
      - name: "Secrets in tracked history"
        description: "Gitleaks, git-history mode"
        scoring_model: FIXED_SCALE
  # ... 15 categories, ~50 criteria total, transcribed from docs/quality-framework.md §4
```

Seeding is **idempotent**: if a `MethodologyVersion` with this `version_label` already exists, nothing is re-inserted.

## 10. Audit creation

For each repo (or sub-project) audited:
1. Resolve `<repo-name>` → filesystem path via `portfolio.yaml`.
2. Upsert the `Repository` row (matched by `path`), creating it on first run.
3. Ensure the "Quality Framework v1.0" `MethodologyVersion` exists (seed if not, per §9).
4. Compute `commit_sha` (`git rev-parse HEAD`) and `is_dirty` (`git status --porcelain` non-empty), create the `Audit` row.
5. Run discovery (§6) and compute the worktree exclusion list (§7).
6. Execute each registered `ToolRunner` (§8, just the throwaway example for 2.0) against each detected sub-project, persisting one `ToolResult` per run.

## 11. Storage decision — raw `ToolResult` payloads

`ToolResult.raw_output` stays exactly as already defined in `radar-core` (JSON column, DB-only) — no separate on-disk file tree for this increment.

**Considered and rejected for now:** storing only a file-path reference in `raw_output` with the actual JSON on disk (motivated by future volume concerns — Trivy/Semgrep outputs can run to hundreds of KB, multiplied across ~20 tools × 10 repos × repeated audits over time). Rejected because:
- `docs/system-design.md`§11 designs storage as a single local SQLite file — splitting introduces a second source of truth (a file can be moved/deleted without the DB knowing) and breaks "one file = the whole state" portability.
- Actual scale (solo developer, 10 repos, periodic audits) is well within what SQLite handles comfortably as TEXT/JSON columns; this isn't a demonstrated problem yet.
- `ToolResult` is already implemented, reviewed, and merged in `radar-core` (sub-project 1/4) — changing its shape now is a migration for a hypothetical, not yet observed, issue.

**Documented future evolution:** if real audit history shows DB bloat becomes a practical problem, add an optional `raw_output_path` column later and offload only large payloads — an isolated, backward-compatible change, not something increment 2.0 needs to solve.

## 12. Execution model & error handling

Sequential execution — one tool at a time, no parallelization. Simpler, sufficient for a solo/local tool, avoids contention on shared `uvx`/`npx`/Docker caches. A tool failure (crash, timeout, unexpected non-zero exit) still produces a persisted `ToolResult` (with its real `exit_code` and available output/stderr as evidence of the failure); the orchestrator logs the error and continues with the remaining tools rather than aborting the audit.

## 13. Testing

Tests use git repos created on the fly inside `pytest`'s `tmp_path` (initialized fresh per test) rather than fixtures against real portfolio repos — isolates tests from `~/projets/`'s real state and from any external tool/network dependency for this increment. Covers: discovery (manifest detection, sub-project splitting), worktree exclusion computation, the throwaway `ToolRunner` end-to-end (discover → run → persist `ToolResult` → `Audit` created), taxonomy seeding idempotency, config loading/validation, and the `--dry-run` path (no DB writes, no tool execution).

**Principle carried forward to category increments (2.1+, not detailed here):** real tool integrations (Semgrep, Trivy, ESLint, etc.) should mock their `ToolRunner`'s output in tests (stubbed JSON matching the tool's real shape) rather than requiring the actual binaries in CI.

## 14. Out of scope for increment 2.0

Deferred to category increments (2.1-2.15):
- Any real `ToolRunner` (Ruff, ESLint, Semgrep, Trivy, PHPStan, etc.)
- Any normalization logic (raw → `Finding`/`Score`)
- Critical penalties (§3.2 of `quality-framework.md`), confidence aggregation, the human-confirmation gate (`PENDING_CONFIRMATION`)
- Parallel tool execution, cross-tool shared caching
- Feeding the computed worktree-exclusion list into an actual tool invocation (no real tool exists yet to receive it)

---

## 15. Global constraints for the implementation plan

- `radar-audit` is a new uv workspace member (root `pyproject.toml`), depending on `radar-core`.
- Python 3.12, `uv`, pytest, ruff + ruff-format + mypy (strict) — same toolchain discipline as `radar-core` (D16), pre-commit hooks extended to cover `radar-audit` alongside the existing `radar-core` scope.
- CLI via Typer.
- Config (`portfolio.yaml`) and taxonomy (`quality_framework_v1_0.yaml`) are YAML, versioned in git (not gitignored — only `radar.db` is).
- No environment-variable overrides for `repos_root` — `portfolio.yaml` is the single source.
- `ToolResult.raw_output` stays DB-only (JSON column) — no filesystem raw-output tree.
- Sequential tool execution; a single tool's failure never aborts the whole audit.
- Tests never depend on real external tools or on `~/projets/`'s actual repos — fixtures are self-contained, created in `tmp_path`.
