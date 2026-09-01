# radar-audit — Category 2 (Code quality) Runners (Increment 2.2) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on increment 2.1 (category 1, merged to `main`), including its post-merge real-world-validation fixes (worktree/`node_modules`/build-output exclusion, `planned_runs()` dedup).
> Spec references: `docs/quality-framework.md`§4.2, `docs/system-design.md`§6 (D12 full definition), `docs/toolchain.md` (Python/JS-TS/PHP/pre-commit-hooks/code-duplication sections), `docs/superpowers/specs/2026-08-28-radar-audit-category-1-architecture-design.md` (structural precedent).

---

## 1. Scope

Second of the fifteen category increments (2.1-2.15, strict numeric order). Covers **category 2, Code quality**, all five criteria:

| # | Criterion | Archetype | Tool(s) | In this increment? |
|---|---|---|---|---|
| 2.1 | Linter clean pass rate | B | Ruff (Python), ESLint (JS, repo's own config), Pint (PHP) | Yes |
| 2.2 | Type-checking pass | B | mypy (Python), tsc/vue-tsc (JS), PHPStan (PHP) | Yes |
| 2.3 | Cyclomatic complexity | A | radon `cc` (Python), ESLint `complexity` rule (JS, audit-owned config), PHPMD `codesize` (PHP) | Yes |
| 2.4 | Pre-commit quality gate | C | Filesystem/config parsing, no external tool (D12 coverage matrix) | Yes |
| 2.5 | Code duplication | A | jscpd (cross-language) | Yes |

No criterion is deferred out of this increment — unlike 1.4 in 2.1, category 2 has no non-deterministic/LLM-judgment criterion.

Eleven `ToolRunner`s total: `RuffRunner`, `EslintLintRunner`, `PintRunner` (2.1); `MypyRunner`, `TypeScriptRunner`, `PhpstanRunner` (2.2); `RadonComplexityRunner`, `EslintComplexityRunner`, `PhpmdComplexityRunner` (2.3); `PreCommitGateRunner` (2.4); `JscpdRunner` (2.5).

## 2. Goal

Repeat the normalization pattern established in 2.1 (raw `ToolResult` → `Finding`/`Score` at criterion level) for category 2. No infrastructure changes are needed to the `ToolRunner` protocol, orchestrator, or data model — the `subproject_path`/`scope`/`supported_stacks`/`timeout_s` extensions built in 2.1 already cover every shape this increment needs, including the two `scope="repo"` runners (2.4, 2.5).

## 3. Resolved design decisions

Three points left ambiguous or unspecified by `quality-framework.md`§4.2 were resolved during design, since implementation cannot proceed on them as written:

**3.1 — PHP's lint/type-check split.** The catalog lists PHPStan for both 2.1 and 2.2, which can't be the same tool run twice for two different criteria without a splitting rule. Resolved: **Pint** (`vendor/bin/pint --test --format=json`, already validated in `toolchain.md`) is 2.1's PHP tool; **PHPStan** (with the Larastan target-mutation workaround, already validated in `toolchain.md`) is 2.2's. This mirrors JS's existing ESLint (lint) / `tsc` (type-check) split, and is also the mapping used by the D12 matrix (§6.4) to classify Pint as a "lint" cell, not "format".

**3.2 — Code duplication bands (2.5).** No numeric bands existed for jscpd's duplicated-line percentage. Resolved (industry-standard SonarQube-style thresholds):

| Duplicated lines | Score |
|---|---|
| ≤3% | 10 |
| 3-5% | 6 |
| 5-10% | 4 |
| >10% | 2 |

**3.3 — Cyclomatic complexity bands (2.3).** No numeric bands existed either. Resolved, based on radon's standard letter-rank complexity buckets, applied to the single most complex function/method found in a sub-project:

| Worst function's complexity | Radon rank | Score |
|---|---|---|
| ≤10 | A/B | 10 |
| 11-20 | C | 6 |
| 21-30 | D | 4 |
| >30 | E/F | 2 |

For JS (`EslintComplexityRunner`) and PHP (`PhpmdComplexityRunner`) to use the same bands, both runners must extract the **actual per-function complexity number**, not a binary pass/fail against one fixed threshold — see §6.

## 4. Runners — 2.1 Linter clean pass rate

**`RuffRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="ruff-check"`)
Invocation: `uvx ruff check --output-format=json <target_path>`. Output is a flat list of violation objects (each with a `filename`); Ruff's JSON reporter does not emit an entry for clean files, so the denominator (`applicable`) is obtained by enumerating the sub-project's own `.py` files (same walk/skip-list convention as `RadonModuleSizeRunner` from 2.1: skip `.venv`, `__pycache__`, `node_modules`, `vendor`, `dist`, `build`, plus threaded `exclude_paths`).

**`EslintLintRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="eslint"`)
Invocation: `npx --package=eslint -- eslint <lint-script-scope> --format json`, using the sub-project's own `package.json` `scripts.lint` target as the scanned path (per `toolchain.md`'s ESLint scope caveat — never a bare `.`, which picks up unrelated generated artifacts). ESLint's JSON reporter emits one result object **per linted file**, clean or not, so `applicable` = `len(results)`, `covered` = results with an empty `messages` array — no separate file enumeration needed, unlike Ruff.

**`PintRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="pint"`)
Invocation: `vendor/bin/pint --test --format=json`, run natively (target's own pinned devDependency, per `toolchain.md`'s note on why Pint/Pest are native rather than ephemeral). Reports per-file pass/fail directly.

## 5. Runners — 2.2 Type-checking pass

**`MypyRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="mypy"`)
Invocation branches on plugin detection, per `toolchain.md`'s Python section: read the sub-project's `pyproject.toml`/`mypy.ini` for a `plugins = [...]` entry first. If absent: `uvx mypy --ignore-missing-imports --output json <target_path>`. If present: `uvx --with-requirements requirements.txt --with mypy mypy --output json <target_path>` (ephemeral install of the target's own runtime deps, same pattern as pytest — needed so mypy can resolve the plugin, e.g. `pydantic.mypy`). Mypy's `--output json` emits one JSON object per diagnostic with a `path`; `applicable`/`covered` computed the same way as Ruff (file walk denominator, since mypy also has no "this file was clean" entry).

**`TypeScriptRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="tsc"`)
Invocation: if the sub-project's `package.json` lists `vue-tsc` as a devDependency, run `npx --package=vue-tsc -- vue-tsc --noEmit`; otherwise `npx --package=typescript -- tsc --noEmit` (per `toolchain.md`'s npx-safety note: the package is `typescript`, the binary is `tsc`). Neither tool has a native JSON reporter — text output in the `file(line,col): error TSxxxx: message` format, parsed with a regex to extract per-file error presence. `applicable` = total `.ts`/`.tsx`/`.vue` files found by the same walk convention as above; `covered` = files with zero parsed errors.

**`PhpstanRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="phpstan"`)
Reproduces the Larastan workaround validated in `toolchain.md`: temporarily `composer require --dev phpstan/phpstan larastan/larastan --no-interaction` inside the **target's own** `<target_path>`, run `vendor/bin/phpstan analyse --configuration <audit-generated extension.neon> --error-format=json`, then **always** restore the target (`git checkout -- composer.json composer.lock && composer install`) in a `try/finally` — this restoration is not best-effort, a crash mid-run must not leave the scanned repo modified. PHPStan's JSON output nests per-file error lists under `files`; `applicable` = total files PHPStan analyzed (from its own output, which — unlike Ruff/mypy — does include entries for clean files), `covered` = files with an empty error list.

## 6. Runners — 2.3 Cyclomatic complexity

**`RadonComplexityRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="radon-cc"`)
Invocation: `uvx radon cc --json <target_path>` (distinct from 1.3's `radon raw`). Output nests a list of block objects per file, each with a `complexity` integer. The runner's job is just to surface this raw JSON; band selection happens in the normalizer (§7).

**`EslintComplexityRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="eslint-complexity"`)
Invocation: `npx --package=eslint -- eslint --no-eslintrc -c <audit-owned config> <target_path> --format json`, using a minimal audit-authored config enabling only the `complexity` rule with `max: 1` — deliberately set to the lowest possible value so ESLint flags **every** function and its violation message includes the function's actual complexity number (`"Function 'x' has a complexity of 14. Maximum allowed is 1."`), which the runner parses out with a regex. This is independent of the target repo's own ESLint config, unlike `EslintLintRunner` (§4) — the same "audit-owned, config-independent" principle `toolchain.md` already applies to radon for Python, so a repo can't inflate its score by not configuring the rule.

**`PhpmdComplexityRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="phpmd-codesize"`)
Invocation: ephemeral isolated Composer scratch project (own `vendor/`, never shared with `PhpstanRunner`'s scratch dir — per `toolchain.md`'s isolated-scratch-per-tool rule, sharing one `vendor/` between PHP tools causes real dependency conflicts), `vendor/bin/phpmd <target_path> xml codesize`. PHPMD has no JSON reporter (`toolchain.md` confirmed only `xml`/`text`/`html` exist); the runner parses the XML `violation` elements, whose message text includes the actual complexity number, same extraction principle as ESLint above.

## 7. Runner — 2.4 Pre-commit quality gate (D12)

**`PreCommitGateRunner`** (`scope="repo"`, no subprocess, `tool_name="pre-commit-gate"`)

Reuses the same domain mapping the orchestrator already computed for sub-project discovery: `python`/`php` sub-project stacks map to domain `"backend"`, `"javascript"` maps to `"frontend"`. Applicable matrix cells = `{lint, format, type-check} × {domains actually present in this repo}` (up to 6).

Detection, in priority order (first config type found wins — no repo in scope combines two):

1. **`.pre-commit-config.yaml`** present at repo root: parse the YAML `repos[].hooks[].id` list. Each recognized hook `id` maps to a `(tool, validator_type)` pair via a fixed lookup table (`ruff`→lint/backend, `ruff-format`→format/backend, `mypy`→type-check/backend, `eslint`→lint/frontend, `prettier`→format/frontend, `vue-tsc`/`tsc`→type-check/frontend). A hook's own `files` regex (when present) narrows which domain it covers; absent a `files` regex, the hook's `id`-implied domain from the lookup table is used directly.
2. **`.husky/`** present (no `.pre-commit-config.yaml`): read every `.husky/<hook-name>` file. If any delegates to `lint-staged` (contains the substring `lint-staged`), chain to `package.json`'s `"lint-staged"` key — a mapping of glob pattern → command list. Each command is matched against the same lookup table (extended with `pint`→lint/backend per §3.1, `phpstan`→type-check/backend), and each glob pattern is checked against the discovered sub-projects' paths to assign a domain.
3. **`lefthook.yml`** present (neither of the above): parsed the same declarative way as `.pre-commit-config.yaml` (per `toolchain.md`'s forward-looking note) — **not smoke-tested against a real config** since no in-scope repo uses it yet; treat any resulting `Score`/`Finding` at `Confidence.LOW` rather than the `HIGH` used for the other two paths.
4. **None found:** status is `TODO`, matrix entirely uncovered.

`RawToolOutput.raw_output` records the full matrix (`{(validator_type, domain): covered_bool}`) plus which detection path was used, for the normalizer to consume.

## 8. Runner — 2.5 Code duplication

**`JscpdRunner`** (`scope="repo"`, no per-sub-project split, `tool_name="jscpd"`)
Invocation: `npx --package=jscpd -- jscpd <repo_root> --reporters json` (single cross-language pass over the whole tree — jscpd's Prism-grammar-based detection natively covers Python/JS/TS/PHP/Vue in one run, unlike the per-stack runners above). Exclusions: same `_ALWAYS_EXCLUDED_DIRNAMES`-style pattern as `DependencyCruiserRunner` (2.1's `node_modules`/`dist`/`build`), reused via jscpd's own `--ignore` glob option, plus the standard worktree `exclude_paths`. Output JSON exposes a `statistics.total.percentage` duplicated-lines figure directly — no manual computation needed.

## 9. Normalization — raw `ToolResult` → `Finding`/`Score`

Same governing rules as 2.1 (`Score` rows at `ScoreLevel.CRITERION` only; missing-data → no `Finding`/no `Score`; `_is_usable`-style guards before trusting a zero-looking result as genuinely clean).

**Multi-sub-project aggregation**, following 2.1's established rules:
- **2.1, 2.2 (archetype B):** `covered`/`applicable` summed across every contributing sub-project and tool, single `score = (covered / applicable) × 10` — same pattern as 1.3's `normalize_module_size`. A monorepo's `covered`/`applicable` combine across `RuffRunner` on `backend/` and `EslintLintRunner` on `frontend/`, for instance.
- **2.3 (archetype A):** worst band across all sub-projects, exactly as 1.1's `normalize_dependency_circularity` — every sub-project's worst-function complexity still generates its own `Finding` even when the aggregate `Score.value` is dominated by one sub-project.
- **2.4, 2.5:** both `scope="repo"`, so never more than one result per audit — no aggregation rule needed, same as 1.2.

**2.1/2.2 — Findings and Score:** one `Finding` per violation/error (`severity=LOW`, `confidence=HIGH` — deterministic tool output), `file` set from the tool's own report. `Score.value = (covered / applicable) × 10`.

**2.3 — Findings and Score:** one `Finding` (`severity=MEDIUM`, `confidence=HIGH` for radon; `confidence=MEDIUM` for the JS/PHP candidates per `quality-framework.md`'s "MEDIUM-pending-smoke-test" baseline until they're validated against a real repo) per function whose complexity exceeds the top band's ≤10 cutoff. `Score.value` = the band (§3.3) matching the sub-project's single worst function, reduced across sub-projects by the worst-band rule.

**2.4 — Findings and Score:** one `Finding` (`severity=LOW`, `confidence=HIGH`, or `LOW` when the `lefthook.yml` path was used per §7) per uncovered matrix cell, naming the missing `(validator_type, domain)` pair. `Score.value`: 10 if `covered == applicable` (`DONE`), 0 if no config detected at all (`TODO`), else `(covered / applicable) × 10` (`IN_PROGRESS`) — exactly D12's status→score mapping. If a repo has no domain at all (shouldn't occur for any in-scope repo but handled defensively), the criterion is `N/A` — skipped, no `Score`.

**2.5 — Findings and Score:** one `Finding` (`severity=LOW`, `confidence=MEDIUM` — jscpd is not yet smoke-tested against a real repo, matching the catalog's "—" confidence pending validation) per duplicate clone pair jscpd reports (capped, like 1.1, at not auto-suppressing intentional patterns — human review happens later via the dashboard, out of scope here). `Score.value` from the bands in §3.2, applied to the repo-wide `statistics.total.percentage`.

All five normalizers attach to the same `ScoringRun` (`get_or_create_scoring_run`, unchanged from 2.1) for the current `Audit` + "Quality Framework v1.0" `MethodologyVersion`.

## 10. Testing

Same "zero mock" discipline as 2.1 — real subprocess invocations against synthetic `tmp_path` git fixtures (`init_git_repo`), no stubbed tool output.

- Each of the 9 subprocess-based runners (all except `PreCommitGateRunner`) needs at minimum: one clean fixture (0 violations / 0 errors / low complexity) and one violating fixture, to exercise both ends of its band/ratio.
- `PhpstanRunner` and `PhpmdComplexityRunner` tests must assert the target fixture's `composer.json`/`composer.lock` are byte-identical before and after the run (the `try/finally` restoration contract from §5/§6 is a correctness requirement, not a nice-to-have — a test that only checks the `ToolResult` and ignores the target's on-disk state would miss a real regression class).
- `MypyRunner` needs both branches of the plugin-detection rule: a fixture with no `plugins` entry (bare `uvx mypy`) and one with a `pydantic.mypy`-style plugin entry (`--with-requirements` path).
- `TypeScriptRunner` needs both branches: a fixture with `vue-tsc` in devDependencies and one without.
- `PreCommitGateRunner` needs one fixture per detection path (§7): a `.pre-commit-config.yaml` repo, a `.husky/` + `lint-staged` repo, and a no-config repo (`TODO` case) — `lefthook.yml` fixture optional/best-effort given it's unvalidated against any real config.
- Normalization tests cover: the summed-ratio rule (2.1/2.2) and worst-band rule (2.3) each with a two-sub-project fixture, the D12 matrix→score mapping (`DONE`/`IN_PROGRESS`/`TODO` cases) for 2.4, and the band lookup for 2.5.
- Per this project's established lesson from 2.1's post-merge fixes: **before considering this increment done, run a real `radar-audit run` against an actual portfolio repo** (Summit-Stats for PHP+Vue, GeoChallenge-Tracker for Python+Vue) and inspect the resulting `Score`/`Finding` rows for plausibility — synthetic fixtures alone did not catch three real bugs in 2.1.

## 11. Out of scope for increment 2.2

- `CATEGORY`/`GLOBAL` level `Score` rows, critical-penalty capping (including P4, category 2's own penalty condition from `quality-framework.md`§3.2), N/A weight-redistribution — still deferred to the same later dedicated aggregation increment noted in 2.1's spec.
- Smoke-testing `EslintComplexityRunner`, `PhpmdComplexityRunner`'s codesize ruleset beyond what `toolchain.md` already validated, and `jscpd` against a real repo ahead of this increment's own implementation — happens during this increment's implementation/testing (§10), not pre-emptively here in the design.
- `lefthook.yml` parsing robustness beyond a best-effort first pass — no in-scope repo uses it; revisit if one adopts it later.
- Recalibrating any of this increment's numeric thresholds (§3.2, §3.3) against real portfolio data — deferred to Phase 5's full-portfolio run, same caveat as 2.1's 30-line/400-LOC thresholds.
- Human-confirmation-gate wiring for P4/D12's false-positive notes (`--no-verify` culture, hook installed but not enforced in CI) — deferred until the dashboard/human-confirmation workflow exists, same as 2.1.

---

## 12. Global constraints for the implementation plan

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration — 2.1 already built every structural piece this increment needs.
- Every `npx` invocation pins its package explicitly (`--package=<exact-name> --`), never a bare binary name, per the dependency-confusion near-miss in `toolchain.md`.
- `PhpstanRunner` and `PhpmdComplexityRunner` never share a scratch Composer `vendor/` directory with each other or with any future PHP tool.
- `PhpstanRunner`'s target-`composer.json` mutation is always restored via `try/finally`, verified by a dedicated test (§10) — never left to best-effort.
- 2.4 and 2.5 runners are `scope="repo"`; the other nine are `scope="subproject"` — matches the `ToolRunner` protocol's existing `scope` field from 2.1, no extension needed.
- Tests use real `npx`/`uvx`/`radon`/`composer` invocations against `tmp_path` git fixtures — no mocking of subprocess or tool output.
- `Score` rows this increment writes are `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is ever created here.
- Numeric bands introduced in §3.2/§3.3 must be marked in code comments/docstrings as resolved-but-provisional (agreed during design, not yet calibrated against real portfolio data), same discipline as 2.1's 1.2/1.3 thresholds.
- Before the increment is marked done, a real `radar-audit run` against at least one PHP+Vue repo (Summit-Stats) and one Python+Vue repo (GeoChallenge-Tracker) must be performed and its output inspected for plausibility, per §10's closing note.
