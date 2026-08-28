# radar-audit — Category 1 (Architecture & design) Runners (Increment 2.1) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on increment 2.0 (core orchestration engine, merged to `main`, PR #14).
> Spec references: `docs/quality-framework.md`§4.1, `docs/toolchain.md` (dependency-cruiser/pydeps/radon sections), `docs/open-decisions.md` D6/D7, `docs/superpowers/specs/2026-08-27-radar-audit-core-engine-design.md`.

---

## 1. Scope

First of the fifteen category increments (2.1-2.15, one per `docs/quality-framework.md`§1 taxonomy category, built in strict numeric order per prior confirmation). Covers **category 1, Architecture & design**, criteria 1.1-1.3:

| # | Criterion | Archetype | Tool | In this increment? |
|---|---|---|---|---|
| 1.1 | Dependency direction / circularity | A | dependency-cruiser (JS/TS), pydeps (Python) | Yes |
| 1.2 | Architectural documentation present | A | filesystem presence/length check, no external tool | Yes |
| 1.3 | Module size distribution | B | radon (Python), static LOC count (JS/PHP) | Yes |
| 1.4 | Consistency of architectural style | A | narrow LLM-judgment layer | **No** — deferred, see §8 |

Five `ToolRunner`s total: `DependencyCruiserRunner`, `PydepsRunner` (1.1), `DesignDocRunner` (1.2), `RadonModuleSizeRunner`, `StaticLocRunner` (1.3). The throwaway `ExampleGitLogRunner` from increment 2.0 is removed.

## 2. Goal

Replace the example runner with real, tested tool integrations for category 1's deterministic criteria, and establish the normalization pattern (raw `ToolResult` → `Finding`/`Score` at criterion level) that increments 2.2-2.15 will each repeat for their own category. Two infrastructure gaps deferred at 2.0 are resolved here because this is the first increment that needs them: sub-project identity on `ToolResult`, and a `timeout_s`/stack-filtering extension to the `ToolRunner` protocol.

## 3. Data model change — sub-project identity on `ToolResult`

`ToolResult` currently has no way to record which sub-project a result belongs to, which breaks correct normalization on monorepos (HexaRot, HiveMind: `backend/` + `frontend/` each produce their own tool runs against the same `Audit`).

**Change:** add `subproject_path: str` (non-nullable) to `radar_core.models.audit.ToolResult`, storing the sub-project's path **relative to the repo root** (`"."` for the repo root itself, `"backend"` / `"frontend"` for a monorepo's children). Relative, not absolute, so results remain comparable across machines/checkout locations.

New Alembic migration, chained after the current head (`555ffc592f67`), adding the column via `op.add_column("tool_result", ...)`. Since this is additive and the table currently has no rows in any real database (increment 2.0 only ever ran the throwaway example against test fixtures), no backfill logic is needed — `nullable=False` with no default is safe for a fresh migration.

`radar_audit.orchestrator.execute_audit` sets `subproject_path` from the `SubProject` it's iterating when constructing each `ToolResult` (see §6).

## 4. `ToolRunner` protocol extension

```python
class ToolRunner(Protocol):
    tool_name: str
    tool_version: str
    supported_stacks: frozenset[str]   # e.g. {"python"}, {"javascript"}; ignored when scope == "repo"
    scope: Literal["repo", "subproject"]
    timeout_s: int

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput: ...
```

- **`supported_stacks`** lets the orchestrator skip a runner for a sub-project whose stack it doesn't handle (e.g. `PydepsRunner` never runs against a `javascript` sub-project), instead of the runner having to detect and no-op internally.
- **`scope`** distinguishes runners that execute once per audited repo (`"repo"` — e.g. `DesignDocRunner`, since `DESIGN.md` lives at repo root, not per sub-project) from runners that execute once per applicable sub-project (`"subproject"` — the other four). `supported_stacks` is meaningless for `scope == "repo"` and is set to `frozenset()` for those runners.
- **`timeout_s`** is passed by each runner to its own `subprocess.run(..., timeout=self.timeout_s)`. A `subprocess.TimeoutExpired` propagates out of `run()` exactly like any other crash and is caught by the orchestrator's existing `_run_tool_safely` (increment 2.0, unchanged) — no orchestrator-level timeout handling needed, the safety net already exists. Per-runner defaults: 60s for `DependencyCruiserRunner`/`PydepsRunner`/`RadonModuleSizeRunner` (first-invocation `npx`/`uvx` package fetch, see §8), 10s for `DesignDocRunner`/`StaticLocRunner` (pure filesystem work).

## 5. Orchestrator changes

`execute_audit`'s inner loop (`for subproject in plan.subprojects: for runner in runners:`) changes to account for scope and stack filtering:

- A `scope == "subproject"` runner runs once per sub-project whose `stack` is in its `supported_stacks`; `target_path` is `subproject.path`.
- A `scope == "repo"` runner runs exactly once per audit (not once per sub-project) against `plan.repository_path`, regardless of how many sub-projects were discovered.
- Every produced `ToolResult` now carries `subproject_path` — `"."` for a repo-scope run or for a sub-project equal to the repo root, else the sub-project's path relative to `plan.repository_path`.

Sequential execution and crash isolation (`_run_tool_safely`) are unchanged from increment 2.0.

## 6. Runners

### 1.1 — Dependency direction / circularity

**`DependencyCruiserRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`)
Invocation: `npx --package=dependency-cruiser -- depcruise --no-config --output-type json <target_path>` (worktree `exclude_paths` fed via `-x/--exclude <regex>`, per `toolchain.md`'s Containers section). `--package=` pinned explicitly, per the dependency-confusion near-miss documented in `toolchain.md` — never a bare `npx depcruise`. Raw output JSON exposes a `modules[]` array; a module's `dependencies[]` entries carry a `circular: bool` flag.

**`PydepsRunner`** (`scope="subproject"`, `supported_stacks={"python"}`)
Invocation: `uvx pydeps <target_path> --show-cycles --no-output`. Raw output is pydeps' cycle report.

### 1.2 — Architectural documentation present

**`DesignDocRunner`** (`scope="repo"`, no subprocess). Checks, at the repo root and in `docs/`: presence of `DESIGN.md` or `ARCHITECTURE.md` (case-insensitive), or a `docs/adr/` / `docs/decisions/` directory containing at least one `.md` file. `RawToolOutput.raw_output` records which file/directory (if any) was found and its line count (blank lines excluded).

### 1.3 — Module size distribution

**`RadonModuleSizeRunner`** (`scope="subproject"`, `supported_stacks={"python"}`)
Invocation: `uvx radon raw --json <target_path>`, giving per-file LOC. Skips common non-source directories (`.venv`, `__pycache__`, `node_modules`, `vendor`, `dist`, `build`) in addition to the threaded worktree `exclude_paths`.

**`StaticLocRunner`** (`scope="subproject"`, `supported_stacks={"javascript", "php"}`)
Pure Python file walk (no external tool — matches `docs/quality-framework.md`§4.1's "static LOC count only" note for JS/PHP), counting non-blank lines per `.js`/`.ts`/`.jsx`/`.tsx`/`.vue` or `.php` file, same directory-skip list as above.

## 7. Normalization — raw `ToolResult` → `Finding`/`Score`

**Scope of normalization for this increment (and, by extension, every category increment): `Score` rows are created at `ScoreLevel.CRITERION` only.** `CATEGORY` and `GLOBAL` level aggregation — weighted averages across criteria/categories, critical-penalty capping (`quality-framework.md`§3.2), N/A weight-redistribution — is explicitly out of scope here and deferred to a single later increment, once all 15 categories have criterion-level normalizers. Computing category/global scores incrementally, category by category, would mean rewriting the same aggregation logic fifteen times and would produce a misleadingly partial `GLOBAL` score before the catalog is fully covered.

**Missing-data handling (`quality-framework.md`§3.4):** if a `ToolResult.exit_code` indicates failure (non-zero, or the `-1`/crash sentinel from `_run_tool_safely`), normalization produces **no** `Finding` and **no** `Score` for that criterion/sub-project. The persisted `ToolResult` (its `exit_code`, `raw_output`) is itself the record of the missing-data condition — no separate "absent" marker is needed.

**Multi-sub-project aggregation (monorepos):** a criterion's model has no sub-project axis (`Score` is one row per criterion per `ScoringRun`), so when more than one sub-project produced evidence for the same criterion (e.g. HexaRot: `PydepsRunner` on `backend/`, `DependencyCruiserRunner` on `frontend/`, both feeding criterion 1.1), the per-sub-project results combine into that single `Score` row:
- **Archetype A criteria (1.1):** the criterion's `Score.value` is the **worst** (lowest) band among all evaluated sub-projects — a repo isn't rewarded for one clean sub-project masking a broken one. Every sub-project's cycles still produce their own `Finding` rows (see below), so the detail isn't lost even when the aggregate is dominated by the worst case.
- **Archetype B criteria (1.3):** `covered`/`applicable` counts are summed across sub-projects before computing the single `score = (covered / applicable) × 10` ratio — natively combinable, unlike archetype A's discrete bands.
- 1.2 is `scope="repo"`, so it never has more than one result per audit; no aggregation rule needed.

**1.1 — Findings and Score:**
One `Finding` per detected cycle (`severity=MEDIUM`, `confidence=HIGH` — deterministic tool output, `status=OPEN`, `human_verdict=UNREVIEWED`), `tool_result_id` set, `file`/`line` from the tool's cycle report where available. Band thresholds are exactly `quality-framework.md`§4.1's table (0=10, 1-2=6, 3-5=4, >5=2) applied to the sub-project's own cycle count, then reduced to the criterion's single `Score.value` per the worst-band rule above. The framework's noted false-positive pattern (intentional bidirectional references, e.g. Vuex store cross-refs) is **not** auto-detected in this increment — cycles are counted as-is; a human can later mark an individual `Finding.human_verdict = FALSE_POSITIVE` once the dashboard exists (not built yet — out of scope, see `TODO.md` Phase 4).

**1.2 — Findings and Score:**
No `Finding` when a non-trivial doc is present (nothing to flag). One `Finding` (`severity=LOW`, `confidence=MEDIUM` — matches the criterion's catalog confidence baseline) when absent or trivial. `Score.value`: 10 if present and non-trivial (≥ 30 non-blank lines — **provisional threshold, not yet calibrated against the real portfolio**, flagged for revision once Phase 5's full-portfolio run gives real distribution data), 6 if present but trivial, 0 if absent entirely.

**1.3 — Findings and Score:**
"Covered" = a module at or under 400 non-blank LOC (Python: radon's `raw` LOC field; JS/PHP: the static walk's line count) — **provisional threshold, same calibration caveat as 1.2's**. One `Finding` per oversized module (`severity=LOW`, `confidence=MEDIUM` — LOC is a weak modularity proxy per the catalog's own note, `file` set to the module path). `Score.value = (covered / applicable) × 10`, `applicable` = total scanned modules across all contributing sub-projects (see aggregation rule above); if `applicable == 0` (no source files found at all) the criterion is skipped entirely for that audit rather than divided by zero — same "no Finding, no Score" treatment as missing data.

**Prerequisite:** all three normalizers attach their `Finding`/`Score` rows to a `ScoringRun` for the current `Audit` + the "Quality Framework v1.0" `MethodologyVersion` (`get_or_create`, matching the model's `(audit_id, methodology_version_id)` unique constraint) — analogous to `orchestrator.get_or_create_audit`'s existing reuse pattern.

## 8. Testing

Same "zero mock" discipline as increment 2.0 and the rest of the codebase: no stubbed tool output, no mocked subprocess calls.

- `DependencyCruiserRunner`/`PydepsRunner`/`RadonModuleSizeRunner` tests invoke the real `npx`/`uvx` commands against small synthetic git repos created in `tmp_path` (`init_git_repo`, the existing helper), including at least one fixture with a genuine circular import (JS and Python each) to exercise cycle detection, and one clean fixture for the 0-cycle path.
- `StaticLocRunner`/`DesignDocRunner` need no subprocess at all — plain `tmp_path` fixtures with files of controlled line counts, and `DESIGN.md`/`ARCHITECTURE.md` present/absent/trivial/non-trivial variants.
- Per D7, `npx`/`uvx` ephemeral installs are not the "network access" D6 gates behind an opt-in flag — D6 targets remote API lookups (GitHub, package registries) done on every run; `npx`/`uvx` just cache a pinned tool version locally on first use, exactly as D7 already describes for every tool in the toolchain. No `--allow-*` flag is introduced for these runners. Practical consequence: these specific tests need network access on their very first run in a fresh environment (empty `~/.cache/uv`/npx cache) — not a new risk, since `radar-audit` already depends on this at real-usage time; just worth knowing before running the suite offline for the first time.
- Orchestrator tests cover: stack filtering (a Python-only sub-project never triggers `DependencyCruiserRunner`), repo-scope de-duplication (`DesignDocRunner` runs once even with multiple sub-projects), and `subproject_path` correctness on the persisted `ToolResult` rows (including the monorepo two-sub-project case).
- Normalization tests cover: the worst-band aggregation rule and the summed-ratio aggregation rule (each with a two-sub-project fixture), missing-data skip on a crashed `ToolResult`, and the zero-`applicable` skip for 1.3.

## 9. Out of scope for increment 2.1

- Criterion 1.4 (narrow LLM-judgment layer for architectural style consistency) — heterogeneous by design (non-deterministic vs. the other three subprocess/filesystem-based criteria); deferred to its own follow-up increment rather than mixed into this one.
- `CATEGORY`/`GLOBAL` level `Score` rows, critical-penalty capping, N/A weight-redistribution — deferred to a later, dedicated aggregation increment (§7).
- Auto-detection of the framework's noted 1.1 false-positive pattern (intentional bidirectional references) — deferred until the dashboard/human-confirmation workflow exists.
- Recalibrating the provisional 1.2/1.3 thresholds (30 lines, 400 LOC) against real portfolio data — deferred to Phase 5's full-portfolio run.
- `--allow-registry-lookup`/`--allow-github-api` opt-in flags (D6/D7's opt-in mechanism) — not needed by any runner in this increment, so not built here; the first increment that needs remote API access builds it then.

---

## 10. Global constraints for the implementation plan

- New Alembic migration for `ToolResult.subproject_path`, chained after `555ffc592f67` (current head).
- `ToolRunner` protocol changes (`supported_stacks`, `scope`, `timeout_s`) are binding for all five new runners and require updating `ExampleGitLogRunner`'s removal (no runner keeps the old two-field-only shape).
- Every `npx` invocation pins its package explicitly (`--package=<exact-name> --`), per the dependency-confusion near-miss in `toolchain.md` — never a bare binary name.
- Tests use real `npx`/`uvx`/`radon` invocations against `tmp_path` git fixtures (`init_git_repo`) — no mocking of subprocess or tool output, consistent with the rest of the codebase.
- `Score` rows this increment writes are `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is ever created here.
- Provisional numeric thresholds (1.2's 30-line minimum, 1.3's 400-LOC "covered" cutoff) must be clearly marked as provisional in code comments/docstrings, not presented as calibrated values.
