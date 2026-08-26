# Quality Framework v1.0

> Status: **frozen, 2026-08-26.** Reviewed point-by-point (taxonomy, scoring archetypes, weights, critical penalties, N/A/missing-data handling, per-category criteria, toolchain gaps) directly with the developer, the same review discipline applied to `open-decisions.md` for Phase 0. This is the reference methodology for Phase 3 (pilot calibration) and beyond, per the versioning rules in §6.
>
> Builds on `docs/system-design.md` (data model §5, confidence system §8, versioning strategy §9 — carried forward unchanged, not repeated here) and `docs/toolchain.md` (validated + candidate tools, Phase 1/Phase 2). Supersedes `system-design.md`§6-7 as the authoritative taxonomy/scoring reference.

---

## 1. Final taxonomy

The 15 categories from `system-design.md`§6 are kept as-is (D8 default: no merge/split without pilot evidence).

```text
1. Architecture & design            9. Observability / operations
2. Code quality                    10. API / UX / product quality
3. Testing & reliability           11. Dependency management
4. Security                        12. Configuration management
5. Maintainability                 13. Data quality
6. Performance                     14. Developer experience
7. DevOps / CI-CD                  15. Technical debt
8. Documentation
```

Three criteria are already frozen from Phase 0 review and are **not redefined below** — see `system-design.md`§6 for their full definition, cited here only by reference:

- **D11** — category 7, "Reverse proxy / local-prod environment parity (Traefik)"
- **D12** — category 2, "Pre-commit quality gate (lint / format / type-check hooks)"
- **D13** — category 10, "Graphic/visual design quality"

Deferred scope flags, unchanged, still not resolved now (D8 default applies — Phase 3 pilot data decides, not a desk decision):
- Category 9 (Observability) — narrowed scope for a solo-developer profile, per §4.9 below.
- Category 10 (API/UX/product quality) — split candidate ("API contract quality" vs. narrower "UX/Visual/product quality"), still provisional.
- Category 13 (Data quality) — narrowed scope for a solo-developer profile, per §4.13 below.

---

## 2. Criterion scoring archetypes

Every criterion below is tagged with one of three archetypes, so the catalog doesn't need to re-derive scoring mechanics per criterion — only the archetype-A criteria need bespoke level conditions.

| Archetype | Scale | When used | Precedent |
|---|---|---|---|
| **A — Anchored** | 0/2/4/6/8/10, each level tied to an explicit evidence-based condition | Judgment-style or tiered-severity criteria | `system-design.md`§7 base rule |
| **B — Coverage** | `score = (covered / applicable) × 10`, computed, not hand-set | Percentage/ratio tool output (lint pass rate, type-check pass rate, test coverage, matrix coverage) | D12's `IN_PROGRESS` formula, generalized |
| **C — Adoption** | 4-state `DONE`(10) / `IN_PROGRESS`(computed or 5) / `TODO`(0) / `N/A`(excluded) | "Is this practice in place" criteria, not a quality gradient | D11, D12 |

All three feed the same weighted-average aggregation (§3). Archetype C's `N/A` and archetype A/B's own N/A conditions both use the identical N/A handling rule (§3) — no separate mechanism.

---

## 3. Global scoring model

Finalizes the placeholders left open in `system-design.md`§7.

### 3.1 Weights

- **Category weights:** deliberately non-uniform, decided 2026-08-26 (not a Phase 3 pilot-derived adjustment, a direct developer priority call — weight is inherently normative, unlike measurement thresholds which need evidence):
  - **Security: 10%**
  - **Testing & reliability: 10%**
  - **Remaining 13 categories: 80/13 ≈ 6.15% each** (equal split of what's left)
  - Total: 100%, by construction.
  - This is still an initial default open to revision, not frozen forever — in particular, category 10's weight (API/UX/product quality, currently carrying the graphic-design criterion at MEDIUM/LOW confidence per D13) is explicitly flagged for future reweighting once/if a criterion providing genuinely quantifiable data becomes available (e.g. a tooled accessibility/visual-regression signal replacing or supplementing the current interpretive layer). Other categories may be revisited the same way as tooling gaps close (§5). Recorded as a MINOR version bump per `system-design.md`§9 unless a future adjustment crosses that section's MAJOR-bump tolerance.
- **Criterion weights within a category:** equal by default unless a catalog entry below states otherwise explicitly.

### 3.2 Critical penalties (concrete list)

Reviewed and confirmed as-is, 2026-08-26. A defined, versioned set of conditions caps a category's score regardless of its weighted average. All four are grounded in tools already validated in `docs/toolchain.md` — no new tooling assumed.

| # | Condition | Evidence | Capped category | Cap |
|---|---|---|---|---|
| P1 | ≥1 confirmed secret found in tracked Git history | Gitleaks (git-history mode, per `toolchain.md`§Security) | Security | ≤ 2 |
| P2 | ≥1 CRITICAL-severity CVE with a known fix version available and not applied | Trivy (fs/image) / pip-audit / `pnpm audit` / `composer audit` | Security | ≤ 4 |
| P3 | A CI workflow exists and runs the test suite, but that job is failing on the default branch (not merely absent) | actionlint + CI-derived test-job status | Testing & reliability | ≤ 4 |
| P4 | A pre-commit/CI quality gate is configured (D12 `DONE`/`IN_PROGRESS`) but errors of the exact type it's meant to block are present merged into the default branch | Ruff / ESLint / PHPStan findings cross-referenced against D12 evidence | Code quality | ≤ 5 |

A capped category still records its uncapped weighted-average value alongside the cap, so the gap itself is visible (not just the final number) — same principle as D12's per-cell `Finding` generation.

### 3.3 N/A handling

Unchanged from `system-design.md`§7, made explicit at both levels: a criterion (or an entire category, e.g. Performance for a profile with no runtime service, see §4.6) marked `N/A` is excluded from its parent's weighted average, its weight redistributed among the remaining applicable members, and the exclusion reason recorded. A repo is never penalized for a criterion or category that plainly does not apply to it.

### 3.4 Missing-data handling

Unchanged from `system-design.md`§7: a criterion that could not be evaluated (tool failed, no evidence available) is recorded as absent, not defaulted to 0 or to N/A, and the category's confidence is downgraded accordingly (§8 minimum-aggregation rule still applies).

---

## 4. Criteria catalog

Per category: objective, archetype, evidence/tool, weight note, confidence baseline, false positives / gaps. Criteria already frozen (D11, D12, D13) are cited, not repeated.

### 4.1 Architecture & design

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 1.1 | Dependency direction / circularity | A | dependency-cruiser (JS/TS), pydeps (Python) — cycle count. 0 cycles=10, 1-2=6, 3-5=4, >5=2 | HIGH | FP: some frameworks (e.g. Vuex store cross-refs) use intentional bidirectional patterns — held at the confirmation gate (`system-design.md`§8) only if it would push the score to its top band |
| 1.2 | Architectural documentation present | A | `DESIGN.md`/`ARCHITECTURE.md`/ADR presence and non-trivial length | MEDIUM | Presence checked, not accuracy against current code |
| 1.3 | Module size distribution | B | radon (Python LOC/complexity proxy); JS/PHP: no dedicated tool validated yet, static LOC count only | MEDIUM | LOC is a weak modularity proxy; full JS/PHP tooling flagged as a gap (§5) |
| 1.4 | Consistency of architectural style | A | Narrow LLM-judgment layer, restricted to "single dominant style vs. visibly mixed" — same discipline as D13's narrow-slice principle | LOW | Human-confirmation gate applies whenever this pushes to the top band |

### 4.2 Code quality

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 2.1 | Linter clean pass rate | B | Ruff / ESLint / PHPStan, findings vs. files scanned | HIGH | Runs against the repo's own config, per `toolchain.md` note on ESLint |
| 2.2 | Type-checking pass | B | mypy / `tsc --noEmit` / PHPStan | HIGH | |
| 2.3 | Cyclomatic complexity | A | radon (Python, validated). JS: ESLint `complexity` rule, audit-owned config (candidate). PHP: PHPMD `codesize` ruleset (candidate) | HIGH (Python) / MEDIUM-pending-smoke-test (JS, PHP candidates identified 2026-08-26, not yet validated) | Candidates added to `toolchain.md`, still gap until smoke-tested (§5) |
| 2.4 | Pre-commit quality gate | C | See D11/D12 — cross-referenced, not redefined | — | |
| 2.5 | Code duplication | A | jscpd (candidate, single tool covering Python/JS-TS/PHP/Vue, MIT to confirm, actively developed) | — | Gap until smoke-tested (§5). Rejected: PMD-CPD (needs a JVM runtime, no advantage over jscpd here) |

### 4.3 Testing & reliability

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 3.1 | Unit tests present & passing, with coverage | B | pytest+coverage / Vitest / Pest, pass rate and coverage % | HIGH | |
| 3.2 | Integration tests | A | Heuristic: test files under an integration-named path, or importing DB/HTTP layers | MEDIUM | Naming-convention-dependent; a repo with a different convention could be under-detected |
| 3.3 | E2E tests | C | Playwright present & wired into CI = `DONE`; present but not in CI = `IN_PROGRESS`; absent = `TODO` for web-facing repos, `N/A` for non-UI repos | MEDIUM | Presence/wiring only, execution not verified in the Phase 1 smoke test (`toolchain.md`) |
| 3.4 | CI executes the test suite | C | actionlint-derived: a workflow step invokes pytest/Vitest/Pest | HIGH | |
| 3.5 | Test quality / relevance | A | Narrow LLM-judgment layer (meaningful vs. tautological assertions) | LOW | Human-confirmation gate applies at the top band |

### 4.4 Security

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 4.1 | Dependency vulnerabilities (CVE) | A | pip-audit / `pnpm audit` / `composer audit`, severity-tiered | HIGH | Feeds P2 (§3.2) |
| 4.2 | Secrets in tracked history | A | Gitleaks, git-history mode | HIGH | Feeds P1 (§3.2) |
| 4.3 | SAST findings | A | Semgrep, severity-tiered | HIGH | FP rate tracked per-rule via D14's `human_verdict` feedback loop |
| 4.4 | Container image vulnerabilities | A | Trivy image scan, HIGH/CRITICAL count | HIGH | `N/A` if no locally built image (`toolchain.md` precondition) |
| 4.5 | Dockerfile hardening | B | Hadolint findings density | HIGH | |
| 4.6a | AuthN/authZ hygiene | A | Semgrep, registry authN/authZ rulesets (`p/security-audit` + framework-specific packs) — candidate, not smoke-tested | — | Coverage likely uneven across FastAPI/Laravel/Vue-Node stacks, to verify at smoke-test; still gap until validated (§5) |
| 4.6b | HTTP security headers | A | mdn-http-observatory (candidate, runtime check against a running server, graded score); fallback candidate `shcheck` (presence-only) | — | Same "needs a running server" precondition as Lighthouse/Playwright; still gap until validated (§5) |

### 4.5 Maintainability

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 5.1 | Complexity hotspots | A | Shares evidence with 2.3, distinct framing: flags outlier files rather than the repo-wide average | HIGH (Python) / MEDIUM-pending-smoke-test (JS, PHP candidates) | Cross-ref 2.3, not double-weighted separately |
| 5.2 | Dead code / unused exports | A | knip (JS, validated). Python: vulture (candidate, MIT, actively maintained). PHP: PHPMD `unusedcode` ruleset (candidate) | HIGH (JS) / MEDIUM-pending-smoke-test (Python, PHP candidates identified 2026-08-26, not yet validated) | vulture reports a per-finding confidence (60-100%) worth surfacing as-is; still gap until smoke-tested (§5) |
| 5.3 | Documentation-in-code (docstring/comment coverage) | B | Python: `docvet` (candidate, MIT, 2026) preferred over `interrogate` (older, maintenance disputed by a competing tool). PHP: `php-censor/phpdoc-checker` (candidate, BSD-2-Clause). JS/TS: no candidate found — existing "coverage" tools there measure TS type coverage, not comment presence | — | Python/PHP: gap until smoke-tested (§5). JS/TS: genuine open gap, no tool identified |

### 4.6 Performance — **partially resolved, backend/DB explicitly out of scope**

Reviewed 2026-08-26: frontend and backend/DB performance are not the same kind of problem and are treated differently, not lumped into one deferred category.

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 6.1 | Frontend performance | A | Lighthouse — score-tiered (90-100→10, 70-89→6-8, 50-69→4, <50→2/0) | MEDIUM | `N/A` for repos with no UI (same population as D13). Candidate tool, **not yet smoke-tested** — added to `docs/toolchain.md` as a candidate pending Phase-1-style validation, same status Playwright already has (needs a running server, build step, headless browser). Doubts worth carrying forward, not glossed over: (a) **reproducibility** — Lighthouse scores are known to vary run-to-run depending on machine load/network conditions, which cuts against the score-stability principle already applied elsewhere (D7); this needs an explicit mitigation (e.g. averaging N runs, or a fixed resource-constrained environment) before the criterion can be trusted at HIGH confidence; (b) **completeness** — Lighthouse's performance score covers page-load metrics (LCP, TBT, CLS, etc.) only, not business-logic or interaction performance, so a high score is a narrow, load-time-only signal, not "this frontend performs well" in the full sense. |

**Backend / DB performance: no criterion defined in v1.0, not `N/A`.** Discussed and decided 2026-08-26: unlike the other gaps in §5 (where a tool is simply missing but the criterion itself is well-defined), backend/DB performance has no agreed-upon *definition* to begin with — there is no objective absolute threshold ("fast enough") without a per-project SLA, and no in-scope repo defines one. The only mechanism that could plausibly work is a **self-referential drift/regression detector** (store a min/max/median baseline per repo at audit time, compare later audits against it) rather than an absolute 0-10 quality score — this reuses the existing `Snapshot` entity (`system-design.md`§5, already scoped for "state at audit time, for trend comparison") but is architecturally different from every other criterion in this framework:

- It cannot produce any signal on a repo's first audit (no baseline yet to compare against).
- It measures *stability relative to the repo's own history*, not absolute quality — a repo that has always been slow would read as "stable", never "bad".
- It requires a reproducible benchmark protocol (which request, which conditions) that no validated tool in `docs/toolchain.md` currently provides.

Given these three structural limitations, backend/DB performance is **excluded from Quality Framework v1.0 entirely, deliberately, not deferred as a tooling gap**. Revisiting it is only worth doing if/when the developer defines concrete, per-project performance targets — at that point the drift-based mechanism above is a plausible starting point, documented here as an idea, not built.

### 4.7 DevOps / CI-CD

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 7.1 | CI presence & health | A | GH Actions workflow present + actionlint clean | HIGH | |
| 7.2 | Reverse proxy / local-prod parity | C | See D11 — cross-referenced, not redefined | — | |
| 7.3 | Container build hardening | A | Shares evidence with 4.4/4.5, DevOps framing ("is the pipeline clean") vs. Security framing ("is the image vulnerable") | HIGH | Cross-ref, not double-weighted |
| 7.4 | Deployment automation | C | `build-push.yml`/`build-deploy.yml` presence, wired to a registry push step | MEDIUM | Presence only, no runtime verification of actual deploys (D6 GitHub API access could later verify run history) |

### 4.8 Documentation

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 8.1 | README completeness | A | Heuristic: standard section headers present (setup, usage, architecture overview) | MEDIUM | |
| 8.2 | Architecture documentation | A | Shares evidence with 1.2, Documentation framing ("present and readable") vs. Architecture framing ("reflects real structure") | MEDIUM | Cross-ref, not double-weighted |
| 8.3 | API documentation | C | OpenAPI/Swagger schema present & served (FastAPI auto-docs, Laravel L5-Swagger); `N/A` for repos with no API | MEDIUM | |

### 4.9 Observability / operations — narrowed scope (per D8/§1 flag)

Deliberately scoped to a solo-developer profile, not an enterprise observability stack.

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 9.1 | Structured logging | A | Heuristic: structured logging library/formatter vs. bare `print`/`console.log` | MEDIUM | Grep-based heuristic, no dedicated tool validated |
| 9.2 | Error tracking integration | C | Sentry SDK (or equivalent) present & configured — real example already observed on Triton (`sentry-sdk` in its deps) during Phase 1 smoke testing | MEDIUM | Presence ≠ correctly wired (e.g. dummy DSN) |
| 9.3 | Health-check endpoint | C | `/health`/`/healthz` route present; `N/A` for repos with no long-lived service (same N/A logic as D11) | MEDIUM | |

### 4.10 API / UX / product quality — provisional (split candidate per D8)

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 10.1 | Graphic/visual design quality | A | See D13 — cross-referenced, not redefined | — | |
| 10.2 | API contract consistency | A | Spectral, built-in `spectral:oas` ruleset (candidate, Apache 2.0, actively maintained) | — | Needs an exported OpenAPI spec file (lighter precondition than a running server, same class as pytest — see `toolchain.md`); gap until smoke-tested (§5) |
| 10.3 | Accessibility (WCAG) | — | Already part of D13's factual layer | — | Not a separate criterion, avoids double-counting |

### 4.11 Dependency management

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 11.1 | Dependency freshness | B | `pip list --outdated` / `npm`&`pnpm outdated` / `composer outdated` (D15, `toolchain.md`) | HIGH | Gated behind D15 opt-in registry access; `N/A` when access isn't granted for a run (never silently scored), and `N/A` for unpinned repos with no lock file per the JobFlow finding in `toolchain.md` |
| 11.2 | License compliance | A | Python: `pip-licenses` (candidate, MIT, actively maintained). JS: `license-checker-evergreen` (candidate, maintained fork). PHP: `composer licenses --format=json` (native, already-validated tool, no new risk) | — | Unlike 11.1, no network call needed (reads already-installed/locked package metadata) — not gated behind D15. Python/JS: gap until smoke-tested (§5); PHP: effectively ready, reuses an already-validated command |
| 11.3 | Dependency footprint | A | Raw dependency count relative to repo size | LOW | No established baseline yet — needs Phase 3 calibration data across the portfolio itself before this criterion is trustworthy |

### 4.12 Configuration management

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 12.1 | Secrets never hardcoded | — | Shares evidence with 4.2, Configuration-management framing ("is config externalized") vs. Security framing ("has a secret already leaked") | HIGH | Cross-ref, not double-weighted |
| 12.2 | Environment separation | A | Heuristic: distinct `.env.example`/`.env.testing`/`.env.prod.example` or equivalent — real example observed on Summit-Stats during Phase 1 | MEDIUM | |
| 12.3 | Config validation at startup | C | Heuristic: Pydantic Settings (Python) / Laravel config validation pattern present | MEDIUM | No dedicated tool validated, code-pattern heuristic |

### 4.13 Data quality — narrowed scope (per D8/§1 flag)

Deliberately scoped to a solo-developer profile, not enterprise data-governance criteria.

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 13.1 | Schema/migration versioning | C | Migrations directory with sequential, timestamped files (Laravel, Alembic, Django) | HIGH | Structural, deterministic |
| 13.2 | Input validation at boundaries | A | Heuristic: Pydantic models on FastAPI routes / Laravel `FormRequest` classes | MEDIUM | No dedicated tool validated (candidate: Semgrep custom rules, not yet built) |
| 13.3 | Test data / fixtures quality | C | Faker/factory pattern present for tests vs. hardcoded literals — real example observed on Summit-Stats (`fakerphp/faker`, factories directory) | MEDIUM | |

### 4.14 Developer experience

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 14.1 | Onboarding documentation | A | `CONTRIBUTING.md` / setup script presence — real example on Summit-Stats (`composer.json` `"setup"` script chaining install+migrate+build) | MEDIUM | |
| 14.2 | Local dev reproducibility | A | Shares evidence with 7.2 (D11) plus Docker Compose dev-profile presence | MEDIUM | Cross-ref, not double-weighted |
| 14.3 | Script/task standardization | A | `package.json`/`composer.json` scripts or `Makefile` covering the common lifecycle (dev, test, lint, build) | HIGH | Structural presence check |

### 4.15 Technical debt

| # | Criterion | Archetype | Evidence / tool | Confidence | Notes |
|---|---|---|---|---|---|
| 15.1 | TODO/FIXME density | A | Grep-based count, normalized per KLOC | HIGH (raw count) / LOW (severity classification) | Density itself is deterministic; classifying a given TODO as real debt vs. legitimate forward-looking note needs a narrow interpretive layer, kept separate from the raw HIGH-confidence signal |
| 15.2 | Dead/unreachable code | A | Shares evidence with 5.2 | HIGH (JS) / MEDIUM-pending-smoke-test (Python, PHP candidates) | Cross-ref, not double-weighted |
| 15.3 | Framework/runtime version currency | A | Engine version pinned vs. actually running — real example already observed during Phase 1 (`npm warn EBADENGINE` on HexaRot/Summit-Stats, a `engines`-vs-installed-runtime mismatch surfaced as a side effect of other tool runs) | HIGH | |

---

## 5. Open gaps carried forward (explicit, not silent)

A repo must never be penalized for a gap that's the audit system's fault, not the repo's. Criteria without a validated tool are scored `N/A` (not 0, not skipped silently) until a future toolchain pass closes the gap:

- **2.3 / 5.1 / 15.2** — cyclomatic complexity and dead-code detection for JS and PHP, plus dead-code for Python. Candidates identified 2026-08-26 (ESLint `complexity` rule in audit-owned config for JS complexity, PHPMD `codesize`/`unusedcode` for PHP complexity+dead-code, vulture for Python dead-code — all added to `toolchain.md`), but none smoke-tested yet, so still counted as a gap until validated.
- **2.5** — code duplication detection. Candidate identified 2026-08-26: jscpd (single tool, Python/JS-TS/PHP/Vue), added to `toolchain.md`, not smoke-tested.
- **4.6a / 4.6b** — authN/authZ hygiene and HTTP security headers. Candidates identified 2026-08-26 (Semgrep registry rulesets for 4.6a, mdn-http-observatory for 4.6b, `shcheck` as a lighter fallback), added to `toolchain.md`, but neither smoke-tested yet.
- **5.3** — docstring/comment coverage. Python (`docvet`, candidate) and PHP (`php-censor/phpdoc-checker`, candidate) identified 2026-08-26, added to `toolchain.md`, not smoke-tested. JS/TS has no candidate at all — existing "coverage" tools there measure TS type coverage, a different metric, not a substitute.
- **10.2** — API contract linting (OpenAPI). Candidate identified 2026-08-26: Spectral (`spectral:oas` ruleset), added to `toolchain.md`, not smoke-tested.
- **11.2** — license compliance. Candidates identified 2026-08-26: `pip-licenses` (Python), `license-checker-evergreen` (JS), `composer licenses --format=json` (PHP, native, already-validated) — added to `toolchain.md`. Python/JS not smoke-tested; PHP effectively ready (no new tool involved).
- **6.1 (Frontend performance)** — Lighthouse is a candidate, not yet smoke-tested (needs Phase-1-style validation: ephemeral install, license, run against an in-scope repo); also carries open reproducibility/completeness doubts, see §4.6.

**Backend/DB performance is not in this list** — reviewed 2026-08-26 and deliberately excluded from v1.0 rather than treated as a tooling gap, see §4.6 for why (no objective definition exists without a per-project SLA that isn't defined anywhere in this portfolio).

These gaps, plus the critical-penalty list (§3.2) and the default equal-weighting scheme (§3.1), are the parts of this framework most likely to move first once Phase 3 pilot data comes in.

---

## 6. Versioning

Identifier: **Quality Framework v1.0**, frozen 2026-08-26, per the format and bump rules in `system-design.md`§9. This is the first `MethodologyVersion` record. Any change after this point (weight rebalancing, gap closure once a candidate tool is smoke-tested, taxonomy merge/split) is a version bump per those rules, not a silent edit of this document.
