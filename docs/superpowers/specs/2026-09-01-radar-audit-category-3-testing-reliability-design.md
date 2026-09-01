# radar-audit — Category 3 (Testing & reliability) Runners (Increment 2.3) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on increment 2.1 (category 1) and increment 2.2 (category 2, code quality), both merged to `main`.
> Spec references: `docs/quality-framework.md`§4.3 (criteria catalog), §3.4 (missing-data handling), §3.5 (evidence freshness), `docs/toolchain.md` (Python/JS-TS/PHP testing sections), `docs/superpowers/specs/2026-08-28-radar-audit-category-1-architecture-design.md` and `docs/superpowers/specs/2026-08-29-radar-audit-category-2-code-quality-design.md` (structural precedent).

---

## 1. Scope

Third of the fifteen category increments (2.1-2.15, strict numeric order). Covers **category 3, Testing & reliability**:

| # | Criterion | Archetype | Tool(s) | In this increment? |
|---|---|---|---|---|
| 3.1 | Unit tests present & passing, with coverage | B | pytest+coverage (Python), Vitest (JS), Pest (PHP) | Yes |
| 3.2 | Integration tests | A | Filesystem/naming-convention heuristic, cross-stack | Yes |
| 3.3 | E2E tests | C | Playwright presence + CI wiring | Yes |
| 3.4 | CI executes test suite | C | Dedicated `.github/workflows/*.yml` parser | Yes |
| 3.5 | Test quality / relevance | A | Narrow LLM-judgment layer | **No — deferred** |

3.5 is deferred out of this increment, the same way 1.4 was deferred out of 2.1: it is explicitly a narrow LLM-judgment layer in the catalog (`quality-framework.md`§4.3), a different implementation track (LOW confidence, human-confirmation gate) from the tool/heuristic-based criteria 3.1-3.4. It will land in its own later increment alongside 1.4.

Six `ToolRunner`s total: `PytestCoverageRunner`, `VitestRunner`, `PestRunner` (3.1); `IntegrationTestRunner` (3.2); `PlaywrightPresenceRunner` (3.3, paired with the shared `CiWorkflowRunner`); `CiWorkflowRunner` (3.3 + 3.4, one runner feeding two normalizers).

## 2. Goal

Repeat the normalization pattern established in 2.1/2.2 (raw `ToolResult` → `Finding`/`Score` at criterion level) for category 3. No infrastructure changes are needed to the `ToolRunner` protocol, orchestrator, or data model — the `subproject_path`/`scope`/`supported_stacks`/`timeout_s` extensions built in 2.1 already cover every shape this increment needs, including the `scope="repo"` runners (3.2, 3.4).

## 3. Resolved design decisions

Four points left ambiguous or underspecified by `quality-framework.md`§4.3 were resolved during design:

**3.1 — Combining pass rate and coverage into one archetype-B score.** The catalog lists two signals (test pass rate, coverage %) under one archetype B formula. Resolved: **pass rate drives the score** (`tests_passed / tests_collected × 10`), consistent with the ratio pattern already established by `normalize_lint_pass_rate`/`normalize_type_check_pass_rate` in 2.1/2.2 (covered/total). Coverage percent is captured in `raw_output`/as informational metadata and surfaces as a `Finding` when below a threshold, but does not itself drive the arithmetic — a red suite makes its own coverage number moot.

**3.2 — CI-test-execution detection tool.** The catalog names actionlint as evidence for 3.4, but actionlint is a YAML/shellcheck syntax linter — it does not answer "which command does this CI step run," which is what 3.4 actually needs. Resolved: a dedicated `CiWorkflowRunner` parses `.github/workflows/*.yml` directly with PyYAML (already a project dependency), scanning every step's `run:` value for test-invocation keywords (`pytest`, `vitest`, `npm test`, `pnpm test`, `pest`, `phpunit`). No new dependency (no Docker), same "read the config directly" pattern already used by `PreCommitGateRunner` (2.4) and `DesignDocRunner` (1.2).

**3.3 — Integration test detection per stack.** No tool produces this signal directly; detection is heuristic, per stack:
- **Python/pytest**: files under a directory named `integration` (e.g. `tests/integration/`), or marked `@pytest.mark.integration`.
- **JS/Vitest**: files under an `integration/` directory, or named `*.integration.test.*` / `*.integration.spec.*`.
- **PHP/Pest**: Laravel/Pest's own convention — files under `tests/Feature/` (as opposed to `tests/Unit/`) are integration tests by construction (they exercise the full HTTP/DB stack); no extra heuristic needed.

**3.4 — Integration test ratio bands.** No numeric bands existed for the integration/total test-file ratio. Resolved (provisional, same discipline as every other increment's bands — not yet calibrated against real portfolio data):

| Integration file ratio | Score |
|---|---|
| 0% | 0 |
| 0-10% | 4 |
| 10-25% | 6 |
| 25-50% | 8 |
| >50% | 10 |

## 4. Runners — 3.1 Unit tests present & passing, with coverage

**`PytestCoverageRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="pytest-cov"`)
Invocation: `uvx --with-requirements requirements.txt --with pytest-cov pytest --junitxml=<tmp>/junit.xml --cov=<target_path> --cov-report=xml:<tmp>/coverage.xml <target_path>` — ephemeral install of the target's own runtime dependencies (same pattern already validated for pytest/mypy in `toolchain.md`), writing both reports to a scratch tempdir (same "write to tempdir, read the file back" pattern as `JscpdRunner`). Per `quality-framework.md`§3.5's evidence-freshness rule, this must always be a live run — a committed `coverage.xml` is never read directly (confirmed necessary by the Summit-Stats pilot finding a stale committed report). Parses JUnit XML for `tests`/`failures`/`errors`/`skipped` counts, and Cobertura-style `coverage.xml`'s root `line-rate` attribute for the coverage percentage.

**`VitestRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="vitest"`)
Invocation: `npx --package=vitest -- vitest run --reporter=json --outputFile=<tmp>/vitest-report.json --coverage --coverage.reporter=json-summary --coverage.reportsDirectory=<tmp>/coverage`, per the npx-safety rule (`toolchain.md`) — never a bare `npx vitest`. The JSON report gives per-test pass/fail counts directly (already validated in `toolchain.md`: 419/419 on GeoChallenge-Tracker); `<tmp>/coverage/coverage-summary.json`'s `total.lines.pct` gives the coverage percentage, read fresh the same way as pytest above (never a committed `coverage-summary.json`).

**`PestRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="pest"`)
Invocation: `vendor/bin/pest --log-junit=<tmp>/junit.xml --coverage --coverage-clover=<tmp>/clover.xml --min=0`, run natively (target's own pinned devDependency, same reasoning as `PintRunner` in 2.1 — Pest measures the repo's own configured test suite, not an audit-owned tool version). `--min=0` disables Pest's own coverage-threshold gate so the runner's exit code reflects test pass/fail only, not an unrelated coverage-percentage gate the target repo might have configured. Parses the JUnit XML the same way as pytest, and Clover XML's `metrics` element for the coverage percentage (`coveredstatements / statements`) — never the committed `coverage.xml` (the exact case `quality-framework.md`§3.5 was calibrated against: Summit-Stats' stale 73.97% vs. a fresh 91.4%).

All three runners' `raw_output` shape: `{"tests": {"total": int, "passed": int, "failed": int, "skipped": int}, "coverage_percent": float}`.

## 5. Runner — 3.2 Integration tests

**`IntegrationTestRunner`** (`scope="repo"`, `supported_stacks={"python", "javascript", "php"}`, `tool_name="integration-test-heuristic"`, no subprocess)

A single filesystem walk from the repo root (same pattern as `StaticLocRunner`'s cross-stack walk in 1.3), classifying every discovered test file by the stack-specific heuristics in §3 above. `raw_output`: `{"total_test_files": int, "integration_test_files": int, "files": [...]}`. Runs once per repo rather than once per sub-project — a monorepo's Python and PHP integration-test ratios are combined into one repo-wide figure, since the heuristic itself is already cross-stack in a single pass, unlike the per-stack subprocess tools in §4.

## 6. Runner — 3.3 / 3.4 CI workflow parsing

**`CiWorkflowRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="ci-workflow"`, no subprocess)

Reads every `.github/workflows/*.yml`/`*.yaml` file with PyYAML, walking each job's `steps[].run` value. Two independent keyword scans over the same parsed content, both recorded in one `raw_output` (avoids parsing the same files twice for two normalizers, the same reasoning `PreCommitGateRunner`'s single-pass detection already established for D12 in 2.2):
- **Test execution** (feeds 3.4): keywords `pytest`, `vitest`, `npm test`, `pnpm test`, `pest`, `phpunit`.
- **Playwright wiring** (feeds 3.3): keywords `playwright test`, `npx playwright test`.

`raw_output`: `{"workflows_found": int, "test_execution_found": bool, "playwright_execution_found": bool}`.

**`PlaywrightPresenceRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="playwright-presence"`, no subprocess)
Checks for `playwright.config.{js,ts}` at the sub-project root, or `@playwright/test` in `package.json`'s `devDependencies`. `raw_output`: `{"present": bool}`.

3.3's normalizer (`normalize_e2e_tests`) is the only one in this increment that reads two different tools' `ToolResult` rows (`playwright-presence` + `ci-workflow`) plus the orchestrator's existing stack→domain mapping (`javascript` → `frontend`, established in 2.2's Task 17) to decide the repo is web-facing at all.

## 7. Normalization — raw `ToolResult` → `Finding`/`Score`

Same governing rules as 2.1/2.2 (`Score` rows at `ScoreLevel.CRITERION` only; missing-data → no `Finding`/no `Score`).

**Multi-sub-project aggregation:**
- **3.1 (archetype B):** `tests_passed`/`tests_collected` summed across every contributing sub-project and tool (`PytestCoverageRunner` on a `backend/` sub-project plus `VitestRunner` on `frontend/`, for instance), single `score = (passed / collected) × 10` — same pattern as 2.1/2.2.
- **3.2, 3.4:** both `scope="repo"`, never more than one result per audit — no aggregation rule needed, same as 2.4/2.5.
- **3.3:** `scope="subproject"` for `PlaywrightPresenceRunner`, but paired with the single repo-wide `CiWorkflowRunner` result. If a repo somehow has more than one `javascript` sub-project, worst-status wins (`TODO` beats `IN_PROGRESS` beats `DONE`), same worst-band precedent as 2.3.

**3.1 — Findings and Score.** One `Finding` per failing/errored test (`severity=LOW`, `confidence=HIGH` — deterministic tool output), `file`/`line` taken from the JUnit XML `testcase` element's `classname`/`file` attributes. One additional informational `Finding` (`severity=LOW`, `confidence=HIGH`) when `coverage_percent` is below 50% — a fixed floor, not a scored band, since §3.1's design decision keeps coverage out of the arithmetic entirely. `Score.value = (tests_passed / tests_collected) × 10`.

**3.2 — Score only, no Findings.** Unlike 2.3/2.5's archetype-A criteria, there is no natural "per-violation" unit here (a ratio has no individual finding to point at, the same way 2.4's fully-covered case has no findings) — no `Finding` rows for this criterion, only the `Score`. `Score.value` from the §3 bands table.

**3.3 — Findings and Score.** One `Finding` (`severity=MEDIUM`, `confidence=MEDIUM`) when the repo is web-facing and Playwright is entirely absent (`TODO`). One `Finding` (`severity=LOW`, `confidence=MEDIUM`) when Playwright is present but not wired into CI (`IN_PROGRESS`). `Score.value`: 10 (`DONE`), 5 (`IN_PROGRESS`), 0 (`TODO`) — matching the catalog's archetype-C status→score convention already used for 2.4's D12. No `Score` row at all when `N/A` (no `javascript` sub-project).

**3.4 — Findings and Score.** One `Finding` (`severity=MEDIUM`, `confidence=HIGH`) when no CI workflow invokes any test command. `Score.value`: 10 if `test_execution_found`, 0 otherwise — always evaluated (never `N/A`), per the error-handling rule in §8.

All four normalizers attach to the same `ScoringRun` (`get_or_create_scoring_run`, unchanged since 2.1) for the current `Audit` + "Quality Framework v1.0" `MethodologyVersion`.

## 8. Error handling / edge cases

- **3.1**: `tests_collected == 0` (pytest exit code 5 "no tests collected", or the Vitest/Pest equivalent of zero discovered tests) → `None` (`N/A`), same logic as 2.2's `normalize_type_check_pass_rate`.
- **3.2**: if the repo has **no test files at all** (0/0 denominator) → `None` (`N/A`) — the "no tests" signal is already carried by 3.1, no need to penalize it twice. If unit tests exist but zero are integration-style, the ratio is a real 0% → band 0, not `N/A`.
- **3.3**: `N/A` if no `javascript` sub-project exists in the repo; otherwise `DONE`/`IN_PROGRESS`/`TODO` per the matrix in §6/§7.
- **3.4**: total absence of any CI workflow file → `TODO` (score 0), never `N/A` — unlike 3.3, nothing structurally prevents any repo from having CI, so its absence is a real gap, not an out-of-scope case.
- Per-runner crash isolation is already guaranteed at the protocol level (`ToolRunner`, since 2.0) — one runner crashing does not affect any other runner in the same audit.

## 9. Testing

Same "zero mock" discipline as 2.1/2.2 — real subprocess invocations (or real file-parsing) against synthetic `tmp_path` git fixtures (`init_git_repo`), no stubbed tool output.

- `PytestCoverageRunner`, `VitestRunner`, `PestRunner` each need at minimum: one fixture with a fully-passing suite, one fixture with at least one failing test, and one fixture with zero collected tests (the 3.1 `N/A` case in §8).
- Per this project's established lesson (2.2's Task 17: exit-code conventions are never safe to assume uniform across tools within one normalizer) — verify each of pytest/Vitest/Pest's actual exit codes empirically against a real clean-fixture and a real zero-tests fixture before hard-coding an "acceptable exit codes" set in the normalizer, the same way 2.2 did for `radon-cc`/`eslint-complexity`/`phpmd-codesize`.
- `IntegrationTestRunner` needs one fixture per stack heuristic (pytest `tests/integration/` dir, pytest `@pytest.mark.integration`, Vitest `*.integration.test.*` naming, Pest `tests/Feature/`), plus the 0/0 no-tests-at-all fixture (§8).
- `CiWorkflowRunner` needs: a workflow invoking pytest/Vitest/Pest (3.4 `DONE`), a workflow invoking Playwright (3.3 signal), a workflow with unrelated steps only (both signals `false`), and a repo with no `.github/workflows/` directory at all (3.4 `TODO` per §8).
- `PlaywrightPresenceRunner` needs a fixture with `playwright.config.ts` present, one with `@playwright/test` only in `devDependencies`, and one with neither.
- Normalization tests cover: the summed-ratio rule (3.1) with a two-sub-project fixture, the band lookup (3.2), and all four `DONE`/`IN_PROGRESS`/`TODO`/`N/A` combinations for 3.3, cross-referencing `PlaywrightPresenceRunner` and `CiWorkflowRunner` results together.
- Per this project's established lesson (2.1's post-merge fixes, reinforced at 2.2's Task 17): **before considering this increment done, run a real `radar-audit run` against an actual portfolio repo** (Summit-Stats for PHP+Vue, GeoChallenge-Tracker for Python+Vue) and inspect the resulting `Score`/`Finding` rows for plausibility — synthetic fixtures alone have not caught every real bug in prior increments.

## 10. Out of scope for increment 2.3

- Criterion 3.5 (test quality/relevance, narrow LLM-judgment layer) — deferred to its own later increment, same treatment as 1.4.
- `CATEGORY`/`GLOBAL` level `Score` rows, critical-penalty capping, N/A weight-redistribution — still deferred to the same later dedicated aggregation increment noted in every prior category's spec.
- Recalibrating the §3 integration-test-ratio bands against real portfolio data — deferred to Phase 5's full-portfolio run, same caveat as every prior increment's provisional thresholds.
- `lefthook.yml`-style non-GitHub CI systems (GitLab CI, CircleCI, etc.) — no in-scope repo uses anything but GitHub Actions; revisit if one adopts a different system later.

---

## 11. Global constraints for the implementation plan

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration — 2.1 already built every structural piece this increment needs.
- Every `npx` invocation pins its package explicitly (`--package=<exact-name> --`), never a bare binary name, per the dependency-confusion rule in `toolchain.md`.
- Coverage and test-result evidence is always a **live run performed by the audit itself**, never a checked-in report file (`coverage.xml`, `coverage-summary.json`, `clover.xml`), per `quality-framework.md`§3.5 — applies to `PytestCoverageRunner`, `VitestRunner`, and `PestRunner` alike.
- `IntegrationTestRunner` and `CiWorkflowRunner` are `scope="repo"`, no subprocess; the other four runners (`PytestCoverageRunner`, `VitestRunner`, `PestRunner`, `PlaywrightPresenceRunner`) are `scope="subproject"` — matches the `ToolRunner` protocol's existing `scope` field from 2.1, no extension needed.
- Tests use real `npx`/`uvx`/`vendor/bin` invocations and real PyYAML parsing against `tmp_path` git fixtures — no mocking of subprocess or tool output.
- `Score` rows this increment writes are `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is ever created here.
- The numeric bands introduced in §3 must be marked in code comments/docstrings as resolved-but-provisional (agreed during design, not yet calibrated against real portfolio data), same discipline as every prior increment's thresholds.
- Before the increment is marked done, a real `radar-audit run` against at least one PHP+Vue repo (Summit-Stats) and one Python+Vue repo (GeoChallenge-Tracker) must be performed and its output inspected for plausibility, per §9's closing note.
