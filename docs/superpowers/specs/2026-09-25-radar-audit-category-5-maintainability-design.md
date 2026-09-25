# radar-audit — Category 5 (Maintainability) Runners (Increment 2.5) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on increments 2.1-2.4 (categories 1-4), all merged to `main`. Binome review is folded into this increment's own subagent-driven-development workflow rather than deferred to a separate pass (process update, 2026-09-24).
> Spec references: `docs/quality-framework.md`§4.5 (criteria catalog), §3.2-3.4 (N/A handling, critical penalties), `docs/toolchain.md` (vulture, docvet, knip, PHPMD, php-censor/phpdoc-checker entries), `docs/superpowers/specs/2026-08-29-radar-audit-category-2-code-quality-design.md` (2.3 cyclomatic complexity precedent, directly reused by 5.1), `docs/superpowers/specs/2026-09-23-radar-audit-category-4-security-design.md` (structural precedent).

---

## 1. Scope

Fifth of the fifteen category increments (2.1-2.15, strict numeric order). Covers **category 5, Maintainability**:

| # | Criterion (exact taxonomy name) | Archetype | Tool(s) | In this increment? |
|---|---|---|---|---|
| 5.1 | Complexity hotspots | A | radon-cc / eslint-complexity / phpmd-codesize (reused from 2.3) | Yes |
| 5.2 | Dead code / unused exports | A | vulture (Python) / knip (JS) / phpmd unusedcode (PHP) | Yes |
| 5.3 | Documentation-in-code (docstring/comment coverage) | B (Python) / A (PHP) / N/A (JS/TS) | docvet (Python) / php-censor/phpdoc-checker (PHP) | Yes |

No criterion is deferred out of this increment. All three candidate tools not yet smoke-tested at design time (vulture, docvet, php-censor/phpdoc-checker) were empirically validated against real code (radar-audit's own source and the Summit-Stats pilot repo) before this spec was written — see §3 for what that validation surfaced.

Five `ToolRunner`s total, three new: `VultureRunner` (5.2, Python), `KnipRunner` (5.2, JS), `DocvetRunner` (5.3, Python), `PhpdocCheckerRunner` (5.3, PHP); one extended in place: `PhpmdComplexityRunner` (now covers both 2.3/5.1's `codesize` ruleset and 5.2's `unusedcode` ruleset in a single invocation). 5.1 introduces no new runner at all — it is a normalizer-only addition that reads the same `ToolResult`s already produced for 2.3.

## 2. Goal

Repeat the normalization pattern established in 2.1-2.4 (raw `ToolResult` -> `Finding`/`Score` at criterion level) for category 5. No infrastructure changes are needed to the `ToolRunner` protocol, orchestrator, or data model — the taxonomy YAML is already fully seeded for category 5 (`quality_framework_v1_0.yaml` lines 104-119), confirmed before design started. This increment's one structural first: it is the first time an existing runner (`PhpmdComplexityRunner`) is extended to feed two different criteria from a single tool invocation, rather than one runner mapping to one criterion.

## 3. Resolved design decisions

Four points left ambiguous, underspecified, or genuinely blocked by tool limitations in `quality-framework.md`§4.5 were resolved during design, all confirmed empirically before being decided:

**3.1 — 5.1's "distinct framing" from 2.3, made concrete.** The catalog says 5.1 shares evidence with 2.3 but frames it differently ("outlier files rather than the repo-wide average") without defining a formula. 2.3's actual implementation (`normalize_cyclomatic_complexity`) already banded on the single *worst* block across the run, not a repo-wide average — so the real available distinction is severity-of-worst-case (2.3) versus breadth-of-the-problem (5.1). Resolved: 5.1 bands on the *count* of blocks exceeding the same complexity threshold already used by 2.3 (`> 10`), not the value of the worst one. This works uniformly across all three tools despite their differing raw-output shapes: radon-cc and eslint-complexity report every scanned block (so outliers are filtered from the full inventory), while phpmd-codesize's `violations` list already contains only over-threshold blocks (so its count is the outlier count directly, no filtering needed). 5.1 does not create new `Finding` rows — 2.3 already flags the worst offender in detail for the same underlying data; duplicating findings for the same evidence under a second criterion would double-report the same code without adding information.

**3.2 — `PhpmdComplexityRunner`'s single-invocation extension.** Confirmed empirically (Summit-Stats, this session) that `phpmd <path> xml codesize,unusedcode` in one invocation produces `<violation>` elements each carrying both `rule="..."` (e.g. `CyclomaticComplexity`, `ExcessiveClassComplexity`, `UnusedLocalVariable`) and `ruleset="..."` (`"Code Size Rules"` vs `"Unused Code Rules"`) attributes — sufficient to cleanly split complexity violations (feeding 2.3/5.1) from dead-code violations (feeding 5.2) from a single XML payload. Resolved: one invocation, not two runners. The runner's `raw_output` tags each parsed violation with its ruleset (e.g. `{"ruleset": "codesize", "complexity": 10, "file": ..., "line": ...}` vs `{"ruleset": "unusedcode", "file": ..., "line": ...}`), and both `_extract_blocks` (2.3/5.1's existing normalizer, updated) and 5.2's new normalizer filter by this tag rather than assuming every entry in `violations` is complexity data. `tool_name` stays `phpmd-codesize` (no rename) to avoid touching the two other places that already key on that exact string (`_USABLE_EXIT_CODES_BY_TOOL` in `cyclomatic_complexity.py`, the `DEFAULT_RUNNERS` registration).

**3.3 — 5.3's PHP-side archetype, forced down to A by a confirmed tool limitation.** `php-censor/phpdoc-checker`'s JSON output (`-j`) is a flat list of *violations only* — classes/methods with a complete, correct docblock never appear in the output at all, in any flag combination (confirmed: `--skip-signatures`, `--info-only`, and combinations of `-x`/`-d`/`-f` were all checked). This makes the total-symbol denominator required for an archetype-B coverage percentage (`covered/applicable`, the same formula docvet supports natively via `presence_coverage`) unobtainable from the tool's own output without reconstructing an independent symbol inventory (e.g. via the bundled `php-parse` AST tool) — a materially heavier addition than the criterion warrants. Resolved: PHP uses archetype A (count-based banding on `class`/`method`-type violations, i.e. fully-undocumented symbols) while Python keeps archetype B (docvet's native `presence_coverage.percentage`). This is a deliberate asymmetry across stacks for the same criterion, justified by a confirmed tool constraint rather than convenience — the DB/YAML taxonomy layer only distinguishes `FIXED_SCALE` (both A and B) from `STATUS_4STATE`, so this split has no schema impact.

**3.4 — Exclusion mechanisms for the two Python tools, confirmed rather than assumed.** `vulture` has a native `--exclude PATTERNS` CLI flag — no gap. `docvet` has no CLI exclude flag at all, but does support `[tool.docvet] exclude = [...]` via `pyproject.toml` (confirmed via `docvet config`, which prints the effective merged config) — resolved by generating an audit-owned scratch `pyproject.toml` populated from `exclude_paths` before invocation, the same pattern already validated for knip's `knip.json` (`toolchain.md`, Phase 3 pilot). Additionally, `vulture` flags two real false-positive classes on radar-audit's own source at its default 60% confidence tier: CLI entrypoints (`main`, decorated `@app.command`/`@app.callback`) and dynamic-dispatch methods (`_parse_*_audit`, called via a lookup table invisible to static analysis). `--ignore-decorators "@app.command,@app.callback"` eliminates the first class cleanly (it is a reliable, tool-native fix); the second class has no generic fix and is tolerated via the same banding-tolerance principle already applied to 2.3/5.1's own noise.

## 4. Runners — 5.1 Complexity hotspots

No new runner. 5.1's normalizer consumes the exact same `ToolResult` rows already produced by `RadonComplexityRunner`, `EslintComplexityRunner`, and `PhpmdComplexityRunner` (registered once in `DEFAULT_RUNNERS`, already dispatched for 2.3 — no double-invocation).

## 5. Runners — 5.2 Dead code / unused exports

**`VultureRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="vulture"`)
Invocation: `uvx vulture <target_path> --ignore-decorators "@app.command,@app.callback" --exclude <patterns>`, mirroring `RadonComplexityRunner`'s `uvx` pattern. `--exclude` patterns built the same way as `RadonComplexityRunner`'s `_SKIP_GLOB_SUFFIXES` plus `exclude_paths`. Vulture has no `--json` mode; output is parsed line-by-line (format: `<file>:<line>: unused <kind> '<name>' (<confidence>% confidence)`) into `raw_output = {"findings": [{"file", "line", "kind", "name", "confidence"}, ...]}`. Usable exit codes: `{0, 3}` (0 = clean, 3 = dead code found — confirmed empirically via minimal fixtures this session; no official vulture doc states this convention).

**`KnipRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="knip"`)
Invocation: `npx --package=knip -- knip --reporter json`, mirroring `EslintComplexityRunner`'s `npx --package=` pattern, `cwd=target_path`. Generates an audit-owned scratch `knip.json` (tempfile, deleted in `finally`, same lifecycle as `EslintComplexityRunner`'s config) with default Vite entry points (`index.html`, `src/main.{js,ts,jsx,tsx}`) to avoid the false-positive-on-real-entry-points caveat already documented from the Phase 3 pilot. If none of the default entry-point candidates exist in the target, the runner returns an empty result (`raw_output = {"issues": []}`) rather than attempting a more sophisticated project-type detection — out of scope for this increment. Defensive JSON-payload extraction (locate the first `{"issues"` prefix in stdout) carried over from the Phase 3 finding about `console.log` pollution in target projects.

**`PhpmdComplexityRunner`** (extended in place, `tool_name` unchanged: `phpmd-codesize`)
Invocation changes from `xml codesize` to `xml codesize,unusedcode` (single pass). XML parsing extended to read the `rule`/`ruleset` attributes per `<violation>` (per §3.2) and tag each parsed entry with `"ruleset": "codesize"` or `"ruleset": "unusedcode"` in `raw_output["violations"]`. `_extract_blocks` in `cyclomatic_complexity.py` (2.3/5.1's normalizer) is updated to filter `raw_output["violations"]` to `ruleset == "codesize"` before building blocks, so the existing 2.3 behavior is unchanged by the extension.

All three: `raw_output["findings"]` (vulture, knip) or `raw_output["violations"]` (phpmd, filtered to `ruleset == "unusedcode"`) feed 5.2's normalizer, which counts entries per tool result and bands the count.

## 6. Runners — 5.3 Documentation-in-code

**`DocvetRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="docvet"`)
Invocation: `uvx docvet --format json presence --all`, `cwd=target_path` (per §3.4, `--all` and a positional path argument are mutually exclusive — confirmed empirically; `--all` scans from `cwd`). Generates an audit-owned scratch `pyproject.toml` (tempfile in `target_path`, deleted in `finally`) with `[tool.docvet] exclude = [...]` populated from `exclude_paths`, passed via `--config <path>`. `raw_output` is the parsed JSON payload as-is (`presence_coverage`, `summary`, `findings` all preserved). Usable exit codes: `{0}` only — docvet exits 0 regardless of findings unless `--fail-on-unavailable` is explicitly set (not used here), so exit code carries no success/failure signal; the normalizer reads `presence_coverage.percentage` directly, never inferring cleanliness from exit code.

**`PhpdocCheckerRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="phpdoc-checker"`)
Invocation: isolated scratch Composer project (per `toolchain.md`'s isolated-scratch-per-tool rule — never shared with `PhpmdComplexityRunner`'s or any other PHP tool's scratch dir), `composer require --dev php-censor/phpdoc-checker` (confirmed canonical package name via Packagist; an earlier guess, `php-censor/php-docblock-checker`, does not exist), then `vendor/bin/phpdoc-checker -d <target_path> -x <exclude_paths joined> -j`. `raw_output = {"findings": [...]}`, the flat JSON array as-is (each entry carries `type`: `class`/`method`/`return-mismatch`/`return-missing`/`param-missing`, per §3.3). Usable exit codes: `{0, 1}` (1 = findings present, confirmed empirically against Summit-Stats).

JS/TS: no runner registered for `supported_stacks`. Per §3.3 and the framework's existing N/A rule (`quality-framework.md`§3.2, no valid tool), this criterion scores permanent `N/A` for JS/TS stacks with no special-case code required — the absence of a registered runner is sufficient.

## 7. Normalizers — banding formulas

All bands below are **provisional, not calibrated against real portfolio data** — same explicit caveat already carried by 2.3's and 2.1's bands.

**5.1 — Complexity hotspots** (`normalize_complexity_hotspots`, archetype A, uniform formula across all three stacks):
`outlier_count` = number of blocks with complexity `> 10` (same threshold as 2.3), per tool.

| outlier_count | Score |
|---|---|
| 0 | 10.0 |
| 1-2 | 8.0 |
| 3-5 | 6.0 |
| 6-10 | 4.0 |
| >10 | 2.0 |

Confidence: identical to 2.3's per-tool mapping (`HIGH` for radon-cc, `MEDIUM` for eslint-complexity/phpmd-codesize). Worst (lowest) score across tools wins when multiple tools report for the same run, same aggregation pattern as 2.3. No new `Finding` rows (§3.1).

**5.2 — Dead code / unused exports** (`normalize_dead_code`, archetype A, same bands across all three stacks):
`finding_count` = number of dead-code findings per tool (vulture `findings`, knip `findings`, phpmd `violations` filtered to `ruleset == "unusedcode"`).

| finding_count | Score |
|---|---|
| 0 | 10.0 |
| 1-3 | 8.0 |
| 4-8 | 6.0 |
| 9-15 | 4.0 |
| >15 | 2.0 |

Confidence: `HIGH` for knip (already validated, Phase 3), `MEDIUM` for vulture and phpmd-unusedcode (candidates, smoke-tested this session but not calibrated in production). One `Finding` per dead-code item (each is a concrete, individually actionable removal candidate, unlike a complexity value) — no cap.

**5.3 — Documentation-in-code** (`normalize_docstring_coverage`):
- Python (archetype B): `value = presence_coverage.percentage / 10`, read directly from docvet's JSON. Confidence `MEDIUM` (candidate, smoke-tested but not production-calibrated).
- PHP (archetype A): `errors_count` = number of `class`/`method`-type findings (fully-undocumented symbols).

| errors_count (PHP) | Score |
|---|---|
| 0 | 10.0 |
| 1-5 | 8.0 |
| 6-15 | 6.0 |
| 16-30 | 4.0 |
| >30 | 2.0 |

Confidence: `MEDIUM`. JS/TS: normalizer returns `None` immediately (no tool_result ever exists for this stack — §6).

## 8. Error handling and N/A

- **Tool execution failures** (timeout, `uvx`/`composer`/`npx` package unavailable, malformed JSON): identical pattern to every existing runner — `RawToolOutput` falls back to `{"stdout", "stderr"}` on `JSONDecodeError`/parse failure, never raises. The normalizer's `_USABLE_EXIT_CODES_BY_TOOL`-style filter (one per new tool, values listed in §5-§6) excludes unusable results from scoring, causing the normalizer to return `None` for that tool while still allowing other tools/stacks in the same run to score — this is a "missing" outcome (runner registered, execution failed), distinct from the JS/TS "N/A" outcome (no runner registered at all) for 5.3.
- **Scratch config lifecycle** (knip's `knip.json`, docvet's `pyproject.toml`): generated as a tempfile inside `target_path`, removed in a `finally` block — identical lifecycle to `EslintComplexityRunner`'s existing `_AUDIT_CONFIG` handling, no new pattern introduced.
- **Isolated scratch Composer projects** (`PhpdocCheckerRunner`): own scratch directory, never shared with `PhpmdComplexityRunner`'s or any other ephemeral PHP tool's scratch dir, per the project's standing isolated-scratch-per-tool rule (a real PHPMD+PHPStan+Larastan dependency conflict was previously hit sharing one scratch dir).
- No new critical-penalty (P1-P4) interaction — category 5 criteria produce `Finding`/`Score` rows at `ScoreLevel.CRITERION` only, same scope boundary category 4 (§1 of that spec) already established for this track.

## 9. Testing plan

Mirrors the existing test structure exactly (`test_radon_complexity_runner.py`, `test_normalize_cyclomatic_complexity.py`, etc.):

- **Per runner** (`test_vulture_runner.py`, `test_knip_runner.py`, `test_docvet_runner.py`, `test_phpdoc_checker_runner.py`, plus an extension of `test_phpmd_complexity_runner.py` for the combined-ruleset invocation): command construction (flags, `--exclude`/`--ignore-decorators`/scratch-config generation and cleanup), parsing of real payloads captured this session (Summit-Stats vulture/docvet/phpdoc-checker output, and radar-audit's own vulture output for the false-positive-filtering case) as fixtures, and edge cases (empty results, malformed JSON, unexpected exit codes).
- **Per normalizer** (`test_normalize_complexity_hotspots.py`, `test_normalize_dead_code.py`, `test_normalize_docstring_coverage.py`): table-driven tests on exact band boundaries (e.g. 2 vs. 3 outliers/findings/errors), the JS/TS `None`/N/A path for 5.3, the "no usable tool_result" `None` path for each criterion, and multi-tool aggregation (worst-of-N for 5.1/5.2 across stacks present in one run).
- No new test infrastructure required — real fixtures captured during this session's empirical validation (§3) seed realistic test data directly.
