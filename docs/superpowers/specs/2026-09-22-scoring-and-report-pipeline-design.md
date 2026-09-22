# radar-audit — Category-level scoring and per-repo report (scope A) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 3/4 (`radar-audit`), pulled forward ahead of full portfolio-wide tooling completion. Builds on increments 2.1/2.2/2.3 (categories 1-3, all merged to `main`), which populate `ToolResult` rows but never invoke any normalizer outside of unit tests.
> Spec references: `docs/quality-framework.md`§3 (aggregation rules, deferred to scope C here), `docs/system-design.md` (pipeline/report component list), `docs/superpowers/specs/2026-08-28-radar-audit-category-1-architecture-design.md`, `2026-08-29-...-category-2-code-quality-design.md`, `2026-09-01-...-category-3-testing-reliability-design.md` (normalizer precedent).
> Feasibility basis: the full 15-category taxonomy is already seeded as data (`seed_taxonomy`, idempotent) regardless of tooling coverage — the only gaps are (1) wiring existing normalizers into a scoring step, and (2) a report generator. Neither requires schema or taxonomy changes.

---

## 1. Scope

This is sub-deliverable **(A)** of a three-step plan agreed with the user:

- **(A) — this spec**: wire scoring for categories 1-3 only (the only categories with runners/normalizers today). Produce a per-repo Markdown report showing real category/criterion scores for categories 1-3, and explicit "not yet audited" placeholders for categories 4-15. No portfolio-wide rollup, no critical-penalty capping, no N/A/missing-data distinction.
- **(B) — later, after (A) is validated**: portfolio-wide `global/*.md` rollup across all audited repos.
- **(C) — reassessed after (B)**: full weighted-aggregation mechanism per `quality-framework.md`§3 (critical penalties, N/A weight-redistribution with reason tracking, confidence downgrade rules).

(B) and (C) are explicitly out of scope for this spec.

## 2. Goal

Turn the already-existing but unused normalizer functions into a real, re-runnable pipeline step, and surface their output as a readable artifact — without inventing any aggregation sophistication beyond what's needed to make categories 1-3 legible today.

## 3. Pipeline shape

Three independent, idempotent commands, each operating on data already in the DB (no repo checkout needed except for `run`):

```
radar-audit run <repo>    → ToolResult rows          (existing, unchanged)
radar-audit score <repo>  → Score rows (CRITERION + CATEGORY)   (new)
radar-audit report <repo> → reports/<repo>/latest.md  (new, gitignored)
```

`score` and `report` can each be re-run at any time; `report` always reflects the latest `ScoringRun` in the DB, not the latest `run` invocation (if `score` hasn't been re-run since a new `run`, `report` shows stale-but-consistent data — no implicit re-scoring).

## 4. Normalizer registry

`radar_audit/normalizers/__init__.py` (currently empty) gains:

```python
CRITERION_NORMALIZERS: dict[tuple[str, str], NormalizerFn]
```

Keyed by `(category_name, criterion_name)` — the same identity pair `normalizers/shared.py::get_criterion` already uses to look up seeded `Criterion` rows, so no new identity scheme is introduced. Populated for the 12 criteria across categories 1-3 that have a normalizer today:

| Category | Criterion | Normalizer |
|---|---|---|
| Architecture & design | Dependency direction / circularity | `normalize_dependency_circularity` |
| Architecture & design | Architectural documentation present | `normalize_design_doc` |
| Architecture & design | Module size distribution | `normalize_module_size` |
| Architecture & design | Consistency of architectural style | *(none — deferred, LLM-judgment)* |
| Code quality | Linter clean pass rate | `normalize_lint_pass_rate` |
| Code quality | Type-checking pass | `normalize_type_check_pass_rate` |
| Code quality | Cyclomatic complexity | `normalize_cyclomatic_complexity` |
| Code quality | Pre-commit quality gate | `normalize_precommit_gate` |
| Code quality | Code duplication | `normalize_code_duplication` |
| Testing & reliability | Unit tests present & passing, with coverage | `normalize_unit_test_pass_rate` |
| Testing & reliability | Integration tests | `normalize_integration_tests` |
| Testing & reliability | E2E tests | `normalize_e2e_tests` |
| Testing & reliability | CI executes the test suite | `normalize_ci_test_execution` |
| Testing & reliability | Test quality / relevance | *(none — deferred, LLM-judgment)* |

A criterion absent from the registry (1.4, 3.5) is not an error — it is the mechanism by which `score` and `report` detect "not yet tooled" without any dedicated DB flag on `Criterion`.

## 5. `score <repo>` command

1. Resolve `Repository` by name; take the most recent `Audit` row for it (by `audited_at`). Error clearly ("no audit found — run `radar-audit run <repo>` first") if none exists. No repo checkout is required — scoring operates entirely on already-persisted `ToolResult` rows.
2. `seed_taxonomy` (idempotent, same call `execute_audit` already makes) to ensure the `MethodologyVersion`/`Category`/`Criterion` rows exist.
3. `get_or_create_scoring_run(session, audit, methodology_version)`.
4. Load all `ToolResult` rows for that audit.
5. For every `(category_name, criterion_name)` key in `CRITERION_NORMALIZERS`: look up the seeded `Criterion`, call the normalizer with the full `tool_results` list (each normalizer already self-filters by `tool_name`, per existing convention). Persist the returned `Score` (`ScoreLevel.CRITERION`) if not `None`.
6. For every category with at least one persisted `CRITERION` `Score` this run: compute a `ScoreLevel.CATEGORY` score as the weighted average of `score.value` over the criteria that got scored, weighted by `criterion.weight`, weight renormalized over just those criteria (so a permanently-unscored criterion like 1.4 or a this-run-`N/A` criterion are treated identically: simply excluded, weight redistributed among the rest). Category `confidence` = the lowest `Confidence` among the contributing criterion scores. A category with zero scored criteria this run gets no `CATEGORY` `Score` row at all.
7. No `ScoreLevel.GLOBAL` row is written in scope (A).

Re-running `score` on the same `Audit` reuses the existing `ScoringRun` (unique on `audit_id` + `methodology_version_id`) and simply adds/updates `Score` rows — the exact reuse pattern `get_or_create_scoring_run` already provides.

## 6. `report <repo>` command

1. Resolve `Repository`, load its latest `ScoringRun` and all associated `Score` rows. Error clearly if none exists ("no score found — run `radar-audit score <repo>` first").
2. Load the full seeded taxonomy (all 15 categories, in `order`, with their criteria) — this is what lets the report show full planned scope even though only categories 1-3 have data.
3. Render Markdown, one section per category in taxonomy order:
   - **Category has a `CATEGORY` `Score`** (1-3 today): heading with score/10 and confidence, then one line per criterion — its score/10 if it has a `CRITERION` `Score`, or "not yet tooled (LLM-judgment layer, deferred)" for 1.4/3.5-style gaps.
   - **Category has no `Score` at all** (4-15 today): heading with "Not yet audited" — no fabricated number, no placeholder score.
4. Header block: repo name, commit SHA, `audited_at`, `scored_at`.
5. Write to `reports/<repo-name>/latest.md` at the Portfolio-Engineering-Radar repo root. Add `reports/` to `.gitignore` — same "generated local artifact, never the source of truth" treatment as `radar.db`, consistent with `system-design.md`'s pipeline diagram (DB → report generator → Markdown, regenerated on demand).

## 7. Error handling

- `score` with no `Audit` for the repo → clear error, non-zero exit, no partial `ScoringRun` created.
- `report` with no `ScoringRun`/`Score` for the repo → clear error, non-zero exit.
- A normalizer raising an exception is not caught specially here — same crash-isolation boundary already established at the `ToolRunner` level does not extend to normalizers in this scope; a normalizer crash surfaces immediately (fail loud, since scope A only touches already-validated category 1-3 normalizers with existing unit-test coverage).
- Category aggregation never divides by zero: a category only gets a `CATEGORY` `Score` when at least one criterion scored (§5.6), so the weight-renormalization denominator is always positive.

## 8. Testing

- Normalizer registry test: every `(category_name, criterion_name)` key resolves to a criterion that actually exists in the seeded taxonomy, and every value is a callable with the expected signature.
- `score` end-to-end test per category (mirroring `test_category_1_end_to_end.py`'s pattern): given a fixture `Audit` with `ToolResult` rows covering a subset of a category's tooled criteria, verify the resulting `CRITERION` `Score` rows, the `CATEGORY` `Score` value (weighted-average arithmetic with a criterion deliberately missing, to verify weight redistribution), and confidence propagation (lowest-of-contributors rule).
- `score` idempotency test: running twice against the same `Audit` reuses the same `ScoringRun` row and does not duplicate `Score` rows.
- `report` test: given `Score` rows for categories 1-3 only, verify categories 4-15 render as "Not yet audited" placeholders, and that 1.4/3.5 render as "not yet tooled" without breaking their category's aggregate.
- No mocking of DB state — real SQLite fixtures via the project's existing test session fixtures, consistent with the "zero mock" discipline from prior increments.

## 9. Out of scope for this spec

- `ScoreLevel.GLOBAL` rows, portfolio-wide rollup (`global/*.md`) — scope (B).
- Critical-penalty capping (P1-P4), formal N/A vs. missing-data distinction with recorded exclusion reason, confidence-downgrade rules beyond the simple "lowest of contributors" — all deferred to scope (C), per `quality-framework.md`§3.
- Criteria 1.4 and 3.5 (LLM-judgment layer) — still deferred as their own later increment, unchanged from 2.1/2.3's original deferral.
- Any dashboard/API work (`radar-api`, `radar-dashboard`) — unaffected by this spec; the Markdown report is the only new artifact.
- Recalibrating any existing scoring bands — untouched, this spec only adds a new caller of already-validated normalizers.

---

## 10. Global constraints for the implementation plan

- No `ToolRunner` protocol changes, no `Score`/`ScoringRun`/`Criterion`/`Category` schema changes, no new Alembic migration — every structural piece needed already exists.
- `score` and `report` are new Typer commands in `radar-audit/src/radar_audit/cli.py`, following the same `_database_url()`/session pattern as the existing `run` command.
- `reports/` is added to `.gitignore` at the Portfolio-Engineering-Radar repo root; report files are never hand-edited or committed.
- Category-level weight redistribution in scope (A) is a simple renormalization over scored criteria only — no distinction between "structurally not tooled" (1.4, 3.5) and "tooled but returned `N/A` this run" is made or needs to be made at this stage.
- `score`/`report` never require the target repo to be checked out on disk — both operate purely against already-persisted DB rows.
