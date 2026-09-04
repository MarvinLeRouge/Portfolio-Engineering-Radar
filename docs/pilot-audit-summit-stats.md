# Second pilot audit — Summit-Stats

> [Version française](pilot-audit-summit-stats.fr.md) | English version

> Manual run, 2026-08-27. Follow-up to the GeoChallenge-Tracker pilot (`docs/pilot-audit-geochallenge-tracker.md`), run at the user's request to check whether Quality Framework v1.0's mechanisms and findings hold up on a structurally different stack: Laravel/PHP + Vue/plain-JS (Summit-Stats) versus FastAPI/Python + Vue/TS (GeoChallenge-Tracker). Same rules as the first pilot: only the tools already validated in `docs/toolchain.md` were run; candidate tools flagged "not smoke-tested" stay out of scope regardless of pilot results. Raw tool outputs live in the session scratchpad, not committed; this document is the durable record.

---

## 1. What was run

| Domain | Tools | Result |
|---|---|---|
| Security | Semgrep, Gitleaks, Trivy (fs + image), composer audit, npm audit | Semgrep clean, Gitleaks 1 finding (false positive, see §3), composer audit 34 advisories (0 CRITICAL tier), npm audit 15 vulns incl. 4 CRITICAL with fix, Trivy image 4 CRITICAL + 55 HIGH (Alpine OS layer) + 13 HIGH (vendor layer), Trivy fs 0 CRITICAL / HIGH-only (contaminated by a stale git worktree, filtered, see §3) |
| PHP | Pint, PHPStan (+Larastan, in-repo, see §3), PHPMD, Pest + coverage | Pint clean, PHPStan level 5 without Larastan: 87 file_errors (mostly noise, see §3); PHPStan+Larastan installed temporarily into the target's own `vendor/` (fix confirmed, see §3): 12 file_errors, real signal; PHPMD (isolated scratch, see §3): 3 real violations, Pest 71/71 passed, 198 assertions, backend statement coverage 91.4% (fresh run; a stale committed `coverage.xml` misleadingly showed 74%, see §3) |
| JS | ESLint, Vitest + coverage | ESLint 0 errors/warnings, Vitest 124/124 passed once scoped away from the polluting worktree (see §3), frontend coverage 100% on the deliberately-narrow `include` scope (components/helpers/stores; pages/router/App.vue covered by E2E instead per `vitest.config.js`) |
| Architecture | dependency-cruiser | 26 modules, 0 cycles, 22 flagged "orphan" — likely a false signal from Vite's `@` alias not resolving under `--no-config`, not verified as real dead code |
| Containers | Hadolint, Trivy (image) | 3 Hadolint findings (Dockerfile), Trivy image as above |
| Git/CI | actionlint | 5 shellcheck-embedded low-severity findings across `build-deploy.yml`/`e2e.yml` |
| Structural heuristics | migrations, factories, README/CONTRIBUTING/DEPLOY/SECURITY, manual API docs, Traefik labels, `.env*` count, TODO density, CI job structure | see §2 |

---

## 2. Category-by-category scoring

Only categories/criteria with direct evidence gathered this pass are scored. 1.4 and 3.5 (LLM-judgment criteria) were evaluated via direct code-reading, mirroring the GeoChallenge-Tracker methodology. 10.1 (graphic design, D13) still needs a rendered-UI pass, not done in this CLI-only run.

### 1. Architecture & design
- 1.1 Dependency direction/circularity — **8** (0 cycles; the 22 "orphan" flags are very likely a dependency-cruiser `--no-config` artifact from the unresolved Vite `@` alias, not confirmed dead code — see §3, held back from a clean 10 pending that confirmation)
- 1.2 Architectural documentation — **8** (no dedicated `DESIGN.md`, but README has a substantive `## Architecture` section plus separate `DEPLOY.md` (666 words) and `SECURITY.md` (283 words) — documentation exists and is split logically, just not under a single canonical file)
- 1.4 Architectural style consistency — **6** (backend is genuinely consistent: all 3 API controllers — `ActivityController`, `StatsController`, `LoginController` — follow the same pattern, reads build Eloquent queries directly in the controller (`Activity::query()->when(...)`), writes delegate to a constructor-injected Service (`ActivityService::store/update/destroy/recalculate`); this is a real, repeated architectural choice, not drift, even though a stricter design would push reads through the service layer too. Frontend is less disciplined: only 1/4 pages (`Activities.vue`) goes through the Pinia store (`useActivitiesStore`); the other 3 — `Dashboard.vue`, `ActivityDetail.vue`, `Login.vue` — call `axios` directly. Net: backend layering is uniform and intentional, frontend data-access is mixed — a real but moderate inconsistency, scoring above GeoChallenge-Tracker's 4 on the strength of the backend pattern, not high enough to call it fully consistent)

### 2. Code quality
- 2.1 Linter clean pass rate — **10** (Pint clean, ESLint 0 errors/warnings)
- 2.2 Type-checking pass — `N/A` (no TypeScript in this repo — plain JS frontend; PHP has no static type-checker validated for this repo, see 2.x tooling note below)
- 2.3 Cyclomatic complexity — **7** (PHPMD, isolated scratch install: only 3 real findings across the whole codebase — `GpxParserService::parse()` at exactly the complexity-10 threshold, `StatsAggregatorService` at overall class complexity 54 vs. a 50 threshold, and one unused local variable. Small, contained hotspots, not systemic. PHPStan+Larastan, run from inside the target's own `vendor/` per the confirmed fix in §3, corroborates this with 12 real findings, none complexity-related — consistent with PHPMD's read that this codebase has no systemic complexity problem)
- 2.4 Pre-commit quality gate — **5 (IN_PROGRESS)** (husky + lint-staged configured: `resources/js/**/*.{js,vue}` → eslint --fix + prettier --write, `**/*.php` → Pint — covers linting/formatting on both sides, but no type-check or test-run step in the pre-commit hook itself, matching the 3/6-cell coverage matrix already documented for this repo in `toolchain.md`)
- 2.5 Code duplication — not scored (jscpd candidate, not smoke-tested)

### 3. Testing & reliability
- 3.1 Unit tests present & passing, with coverage — **9** (Pest 71/71 backend passed, 198 assertions, fresh coverage run 91.4% statements, above the repo's own 80% CI gate; Vitest 124/124 frontend passed once scoped away from worktree pollution, 100% on its deliberately-narrow `include` set. Held at 9 rather than 10 only because the committed `coverage.xml` is stale/misleading if trusted directly, see §3 — a process risk, not a suite-quality issue)
- 3.3 E2E tests — **8 (IN_PROGRESS)** (dedicated `e2e.yml`: real Playwright suite against a docker-compose CI stack, seeds a user via artisan, issues a Sanctum token, does an actual HTTP smoke-test upload against `/api/activities` with a real GPX fixture before running the full Playwright job — a notably more realistic E2E setup than GeoChallenge-Tracker's "configured but not wired into CI" state; not full 10 only because it's a separate workflow gated on `push` to `main`, not part of the main `ci.yml` merge gate)
- 3.4 CI executes the test suite — **10** (`ci.yml`: `tests` job runs `php artisan test --coverage --min=80` (fails the build under threshold) + Pint/ESLint lint steps; `frontend-unit` job runs `npm run test:coverage`; both upload to Codecov with distinct `backend`/`frontend` flags)
- 3.5 Test quality/relevance — **9** (sampled `ActivityStoreTest.php`: real GPX fixture files, `assertDatabaseHas`, explicit key-shape assertions, dedicated 422-validation-error tests for missing file and invalid type — not tautological. Grep across the full suite found 1/228 backend weak assertions and 0/77 frontend weak assertions — an even cleaner ratio than GeoChallenge-Tracker's already-strong 0/1861 and 4/598. No orphaned/uncollected test files found this pass, unlike GCT's 4 underscore-prefixed files)

### 4. Security
- 4.1 Dependency vulnerabilities — **4** (composer audit: 34 advisories, 8 HIGH/21 MEDIUM/4 LOW, no CRITICAL tier in composer's own severity model — notably a much larger raw count than GCT's single pip-audit finding, though a Packagist cross-check confirmed a fix is available for `laravel/framework` within the existing `^12.0` constraint (installed v12.54.1, latest 12.x is v12.68.0), so most of this is plain staleness, not unfixable debt; npm audit: 15 vulns, 4 CRITICAL all with a fix available — this is the concrete P2 trigger, see below)
- 4.2 Secrets in tracked history — **10** (0 real secrets; Gitleaks' 1 raw hit is the same example-file false-positive class already documented for GeoChallenge-Tracker, see §3)
- 4.4 Container image vulnerabilities — **2 (uncapped: see below)** (Alpine 3.23.3 OS layer: 4 CRITICAL with a fix available + 55 HIGH — this is a second, independent P2 trigger; `vendor/composer/installed.json` layer: 13 HIGH, no CRITICAL)
- 4.5 Dockerfile hardening — **7** (3 Hadolint findings, low-severity, similar profile to GeoChallenge-Tracker's backend Dockerfile)

**Critical penalty check (§3.2):** P1 does **not** trigger (0 real secrets, see §3). **P2 triggers**, and via two independent sources this time, matching GeoChallenge-Tracker's pattern exactly: npm audit found 4 CRITICAL with a fix available (source-dependency evidence) AND Trivy's image scan independently found 4 CRITICAL with a fix available on the same Alpine/Node layer (build-artifact evidence). Per `quality-framework.md`§3.2, category score is capped at **4** (uncapped average of the 4 scored criteria above: 5.75). This is the same mechanism confirmed twice now on two structurally different repos, via two independent evidence sources each time — strong calibration signal that P2 is not a one-off artifact of GCT's specific dependency tree.

### 7. DevOps / CI-CD
- 7.1 CI presence & health — **10** (3-workflow setup: `ci.yml` (tests+lint, coverage-gated), `e2e.yml` (Playwright against a real docker-compose stack), `build-deploy.yml` (GHCR build + SSH deploy) — actionlint clean apart from 5 minor shellcheck notes)
- 7.2 Reverse proxy / local-prod parity — **10** (D11: Traefik labels correctly differentiated — dev uses the `web` entrypoint over plain HTTP on `summit-stats.marvinlerouge.local`, prod uses `websecure` with `tls=true`/`tls.certresolver=letsencrypt`, both sharing the external `traefik-public` network — textbook DONE, identical pattern to GeoChallenge-Tracker)
- 7.4 Deployment automation — **10** (`build-deploy.yml`: builds and pushes both `app` (PHP-FPM) and `nginx` images to GHCR with a `sha-`-tagged + `latest` scheme, then deploys over SSH via `appleboy/ssh-action`, pulling the versioned `docker-compose.prod.yml` and recycling the stack — a notably more complete CD pipeline than GeoChallenge-Tracker's build-and-push-only workflow, since it also handles the deploy step)

### 8. Documentation
- 8.1 README completeness — **10** (2287 words: installation, architecture, API endpoint table, CI/CD, OSM tile proxy cache, and more; plus a maintained `README.fr.md`, `CHANGELOG.md`, `CONTRIBUTING.md` (449 words), `DEPLOY.md` (666 words), `SECURITY.md` (283 words) — a noticeably richer documentation surface than GeoChallenge-Tracker's README-only setup)
- 8.3 API documentation — **4** (no OpenAPI/Swagger — Laravel has no FastAPI-equivalent auto-docs generator wired in; README's `## API endpoints` section is a manually-maintained markdown table with example request/response, which is real but not machine-readable/interactive and will drift from the actual routes over time, unlike GeoChallenge-Tracker's automated Swagger)

### 9. Observability / operations
- 9.1 Structured logging — not directly sampled this pass (Laravel's default `Log` facade is available but no explicit structured/JSON channel configuration was checked); leaving unscored rather than guessing
- 9.2 Error tracking integration — **0 (TODO)** (no Sentry or equivalent found in `composer.json`/`package.json`, same gap as GeoChallenge-Tracker)
- 9.3 Health-check endpoint — **0 (TODO)** (no `/health` or equivalent route in `routes/api.php`/`routes/web.php` — unlike GeoChallenge-Tracker's `/health` + `HealthCheck` response model, this is a real, confirmed gap)

### 11. Dependency management
- 11.1 Dependency freshness — `N/A` this pass (D15 registry-lookup opt-in not systematically exercised; the one spot-check done — `laravel/framework`, fix available within constraint — was for the 4.1 P2/fix-availability check, not a full freshness pass)
- 11.3 Dependency footprint — not scored (no portfolio baseline yet, per the criterion's own note)

### 12. Configuration management
- 12.2 Environment separation — **10** (5 distinct `.env*` files: `.env`, `.env.example`, `.env.prod.example`, `.env.testing`, `.env.e2e` — a finer-grained separation than GeoChallenge-Tracker's 3-file setup, reflecting the extra CI/E2E environment)
- 12.3 Config validation at startup — **2** (no fail-fast validation found — `AppServiceProvider::boot()` is empty, only DI bindings in `register()`; Laravel's own `config/*.php` files read `env()` with defaults but don't assert required values are set, unlike GeoChallenge-Tracker's Pydantic-Settings fail-fast pattern — real, confirmed gap, not a tooling blind spot)

### 13. Data quality
- 13.1 Schema/migration versioning — **10** (10 Laravel migration files present — a real, versioned schema-migration mechanism, in clear contrast to GeoChallenge-Tracker's confirmed 0/TODO on this same criterion for its schemaless MongoDB setup)
- 13.3 Test data/fixtures quality — **10** (4 Eloquent factories — `ActivityFactory`, `SegmentFactory`, `TrackPointFactory`, `UserFactory` — actively used in Pest tests via `User::factory()->create()`, plus real GPX fixture files under `tests/Fixtures/gpx/`; again a clear contrast to GeoChallenge-Tracker's confirmed 0/TODO, which used inline literals instead)

### 14. Developer experience
- 14.1 Onboarding documentation — **10** (`CONTRIBUTING.md` present (449 words) plus README's detailed `## Installation` section)
- 14.3 Script/task standardization — **10** (`composer.json`/`package.json` scripts cover dev/test/lint/build; husky + lint-staged wire linting into the commit path)

### 15. Technical debt
- 15.1 TODO/FIXME density — **0 occurrences** across `app/` and `resources/js/` (raw count only, no KLOC normalization or severity classification done this pass, consistent with the GCT methodology)
- 15.3 Framework/runtime version currency — **8** (Laravel `^12.0` installed at v12.54.1, latest 12.x is v12.68.0 — current major, a few minor versions behind but within the declared constraint and easily bumped; PHP `^8.2`, Node 20 in CI — all current-generation, nothing end-of-life)

---

## 3. Calibration findings — false positives and tool-invocation corrections

As with GeoChallenge-Tracker, these are the actual value of this pass: places where the frozen framework or the validated toolchain needs a correction, plus explicit cross-repo consistency checks against the first pilot's findings.

### 3.1 Gitleaks: the example-config false-positive pattern recurs exactly as documented for GeoChallenge-Tracker

The 1 Gitleaks hit is a `generic-api-key` match on `.env.prod.example` (a template file, not a real environment file — matched a value like `BCRYPT_ROUNDS=12`, not an actual secret). Same class already flagged in the first pilot's §3.1 recommendation (test-fixture pre-filter for P1). **Cross-repo consistency signal:** this confirms the false-positive pattern isn't specific to GeoChallenge-Tracker's test-token style — it generalizes to any example/template config file with plausible-looking values. Recommend broadening the §3.1 correction from "test file" patterns to also cover `.env.*.example`/`.env.*.template`/`.env.*.sample` file-path patterns.

### 3.2 Larastan is incompatible with the ephemeral/audit-owned installation pattern (D7) — root cause confirmed, fix validated

Installing PHPStan + Larastan into an audit-owned scratch Composer project (per D7's "audit pins/installs its own tool versions independent of the target repo") and pointing it at Summit-Stats' `app/` via an absolute path fails with `Undefined constant "Larastan\Larastan\LARAVEL_VERSION"`. This is **not** a scan-scope problem — excluding `vendor/`/framework folders from the analyzed `paths` doesn't touch it, because the failure happens while Larastan's `extension.neon` is being parsed, before any file is even selected for analysis. The actual mechanism: Larastan resolves the target's Laravel version and loads the matching stub set by introspecting the app's *own* installed `vendor/`/`composer.lock` — an unrelated scratch Composer project has nothing to introspect, no matter what path is scanned.

**Fix confirmed by direct test:** temporarily add `larastan/larastan` as a `require-dev` inside Summit-Stats' own `composer.json` (`composer require --dev phpstan/phpstan larastan/larastan --no-interaction`), run `vendor/bin/phpstan` from there with an `extension.neon` include, then revert `composer.json`/`composer.lock` and re-run `composer install` to restore the repo exactly as it was (verified clean via `git status` before and after). Result: the 87 file_errors of mostly-noise from the plain-PHPStan fallback dropped to **12 file_errors of real signal** — an unused class constant, generic-type mismatches on two Eloquent relation return types, a potential null-safe-call issue on `toDateTimeString()`, and by-reference parameter warnings in `StatsAggregatorService`. This is a genuine, now-documented exception to D7: Laravel-aware static analysis structurally requires running inside the target's own dependency tree, not the fully-isolated pattern that works for every other ephemeral PHP tool. **Correction applied to `toolchain.md`:** documented, including the revert step so the audit never leaves a footprint in the scanned repo.

### 3.3 Each ephemeral PHP tool needs its own isolated Composer scratch project

Installing PHPMD into the same scratch directory already used for PHPStan+Larastan caused a fatal Composer dependency conflict (`PDepend\DependencyInjection\PdependExtension::load(...)` incompatible with the Symfony DI version Larastan's tree pulled in) — not a PHPMD bug, a transitive dependency clash between two unrelated tools sharing one `vendor/`. **Fix:** a brand-new, fully isolated scratch project (`/tmp/phpmd-scratch`, PHPMD only) resolved cleanly. **Correction needed for `toolchain.md`:** each ephemeral PHP tool (PHPStan, PHPMD, Pint if ever run standalone, etc.) must get its own isolated Composer scratch project — never share one `vendor/` across multiple static-analysis tools, even though this is more setup overhead than the JS/TS side (where `npx <tool>` avoids the shared-`node_modules` equivalent of this problem).

### 3.4 `.claude/worktrees/` is a generalized recursive-discovery pitfall, not a Dockerfile-only edge case

Phase 1 documented this only for Dockerfile discovery. This pass found it independently breaks two more tools on the same repo:
- **Vitest** silently double-counted every test (62 real → 124 reported) because `vitest.config.js`'s `test.exclude` covers `node_modules/**` and `e2e/**` at the repo root, but not `.claude/worktrees/**`, which contains its own nested copy of both `resources/js/__tests__/` and `e2e/`.
- Worse than double-counting: `npm run test:coverage` (which invokes the full Vitest run without a path filter) **hard-fails** with `Playwright Test did not expect test.describe() to be called here` — Vitest picks up `.claude/worktrees/.../e2e/upload.spec.js`, a Playwright spec file, and crashes on the `test.describe()` API mismatch between the two test runners. This isn't a cosmetic double-count, it's a full run failure.
- **Trivy fs** scan similarly double-counted CVEs from `composer.lock`/`package-lock.json` duplicated inside the worktree.

**Fix used this pass (ad hoc):** filtered result JSON to exclude any path containing `.claude/worktrees`, and separately re-ran Vitest scoped to `resources/js` explicitly (`npx vitest run --coverage resources/js`) to sidestep the Playwright crash entirely. **Real fix, confirmed after the fact:** this is fully filterable per tool, not a case needing a manual/skip-tool fallback. Every recursively-scanning tool in this toolchain has a native exclusion mechanism, checked directly against each one's own `--help`: `find` (`-not -path`), Vitest (`--exclude <glob>`), `trivy fs`/`trivy image` (`--skip-dirs`), dependency-cruiser (`-x/--exclude <regex>`), ESLint (`--ignore-pattern`), PHPMD (`--exclude`), PHPStan (`excludePaths` in its neon config). The exclude list shouldn't be hardcoded to `.claude/worktrees` either — `git worktree list --porcelain` gives the exact worktree paths for any repo, so the audit can compute the exclude list once per repo and feed it into whichever mechanism each tool supports. **Correction applied to `toolchain.md`:** generalized the existing Dockerfile-discovery note into this repo-wide rule, with the concrete per-tool flags and the `git worktree list` approach. This is now confirmed on 2/2 piloted repos that happened to have an active worktree at audit time.

### 3.5 A committed `coverage.xml` can be stale and misleading — always regenerate rather than trust a checked-in artifact

The repo's committed `coverage.xml` showed 537/726 statements covered (73.97%), which would read as *below* the repo's own 80% CI gate — a concerning finding at first glance. Re-running `vendor/bin/pest --coverage` fresh produced 91.4%, comfortably above the gate. The committed file was simply stale (from an earlier point in the repo's history, not regenerated since). **Correction needed for `toolchain.md`/orchestration:** coverage criteria (3.1, and any future coverage-threshold criterion) must always regenerate coverage output from a live test run, never read a checked-in `coverage.xml`/`coverage-summary.json` as ground truth, even when one is present in the repo. Worth a one-line note in `toolchain.md`'s Testing section — this is a new finding, not previously documented from GeoChallenge-Tracker's pass (GCT's coverage % was already flagged there as "not extracted this pass", which in hindsight was the safer default).

### 3.6 PHPStan-on-Eloquent noise is the same structural class as GeoChallenge-Tracker's ESLint-on-generated-artifacts noise

Both are cases of "raw tool output needs domain-aware config or scope-filtering before being trustworthy for scoring": GCT's 42 ESLint errors were 100% noise from accidentally-scanned `.venv`/`htmlcov` artifacts; Summit-Stats' 87 PHPStan file_errors (without Larastan) are majority noise from Eloquent's dynamic `$model->property` magic and Laravel's global helper functions (`config()`, `request()`, `database_path()`) not being recognized without Larastan's stub files. Different root cause (missing Laravel-aware stubs vs. wrong scan scope), same lesson: PHPStan-without-Larastan on a Laravel repo should not be trusted for a 2.x complexity/quality score. With §3.2's fix applied, the noise drops away (12 real findings instead of 87), so this is now a solved case rather than an open caveat.

---

## 4. Open items not resolved by this pass

- **10.1 (graphic design, D13)** — not evaluated, same as GeoChallenge-Tracker; needs a rendered-UI browser pass.
- **9.1 (structured logging)** — deliberately left unscored rather than guessed; needs a direct read of actual `Log::` call sites and `config/logging.php` channel config, not done this pass.
- **2.2 (type-checking)** — correctly `N/A`: this repo has no TypeScript; PHP now has a validated path (PHPStan+Larastan run in-repo per §3.2) but it wasn't scored under 2.2 this pass since the criterion wasn't re-run specifically for a type-checking verdict, only cross-used for 2.3's complexity corroboration.
- **11.1 (dependency freshness)** — correctly `N/A` beyond the one spot-check done for the 4.1/P2 cross-reference; D15's registry-lookup opt-in wasn't systematically exercised.
- **Category 6 (Performance)** — correctly out of scope, same reasoning as GCT (Lighthouse unvalidated, backend/DB performance excluded from v1.0 per `quality-framework.md`§4.6).

---

## 5. Cross-repo consistency assessment

Answering the question this second pilot was run to answer: does Quality Framework v1.0 behave consistently across two structurally different repos?

**Yes, with high confidence.** Concrete evidence:

1. **The P2 critical-penalty mechanism triggered independently on both repos**, each time via two separate evidence sources (GCT: Trivy image + the first pass's fix-availability cross-check; Summit-Stats: npm audit + Trivy image, on the very same Alpine/Node layer type both repos happen to share on their frontend). This is the framework's highest-stakes mechanism (it caps an entire category's score) and it fired correctly, for the right reason, on unrelated dependency trees both times.
2. **The Gitleaks example-file false-positive class recurred exactly**, strengthening (not just confirming) the §3.1 recommendation from the first pilot — it's now clearly a pattern worth a real pre-filter, not a one-off quirk of GCT's test suite.
3. **A structurally identical "raw tool output needs scope-awareness" failure mode recurred** (§3.6) with a different tool and different root cause, suggesting this is a general property of static-analysis tooling on real repos, not something specific to Python/JS.
4. **Genuinely different, repo-specific findings scored as expected** rather than defaulting to similar numbers: 13.1/13.3 (migrations/factories) flipped from GCT's 0/TODO to Summit-Stats' 10, exactly reflecting the real difference between a schemaless MongoDB app and a Laravel/Eloquent app — the framework didn't flatten a real architectural difference into a false equivalence.
5. **One new, valuable finding emerged that GCT's pass didn't surface**: the `.claude/worktrees/` discovery pitfall, previously scoped only to Dockerfile discovery in Phase 1, is now confirmed as a general recursive-discovery risk (Vitest, Trivy fs) — exactly the kind of generalization a second pilot is meant to catch that a single pilot can't.

No taxonomy, weight, or scoring-model change is warranted from this pass. All findings in §3 are toolchain-invocation precision fixes (Larastan's in-repo install requirement, isolated Composer scratch projects, worktree exclusion, coverage regeneration), the same category of correction the first pilot produced — reinforcing that Phase 3's job (harden invocations before Phase 4 automates them) is on track, not that the framework itself needs rework.

---

## 6. Recommended framework corrections (for `quality-framework.md` / `toolchain.md`)

All six corrections below have been applied directly to `quality-framework.md`/`toolchain.md` as of this pass (not left as future work):

1. **`quality-framework.md`§3.2 P1 condition** — broadened the GCT-derived test-fixture pre-filter to also cover `.env.*.example`/`.env.*.template`/`.env.*.sample` file-path patterns, per §3.1 here. Applied.
2. **`toolchain.md` PHP/Laravel section** — replaced the open "config decision needed" note with the confirmed fix from §3.2: Larastan must be temporarily installed into the target's own `vendor/` (not D7's isolated scratch pattern), with the exact revert step so no footprint is left in the scanned repo. Applied.
3. **`toolchain.md` PHP section** — documented the isolated-scratch-per-tool requirement from §3.3: never share one Composer scratch project across multiple ephemeral static-analysis tools. Applied.
4. **`toolchain.md` Containers section** — generalized the existing Dockerfile-only `.claude/worktrees` note (§3.4) into a repo-wide exclusion rule, with the confirmed native exclude flag for every recursively-scanning tool in the toolchain and the `git worktree list --porcelain` approach for computing the exclude list dynamically per repo, rather than hardcoding `.claude/worktrees`. Applied.
5. **`toolchain.md` Python section** — added a cross-language rule that coverage criteria must always regenerate from a live test run, never trust a checked-in `coverage.xml`/`coverage-summary.json` (§3.5). Applied.
6. **`quality-framework.md`§3.5 (new subsection, "Evidence freshness")** — formalized the coverage-regeneration rule as a global methodology rule, not just a `toolchain.md` operational note: any criterion whose evidence could be read from a checked-in, tool-generated artifact must instead come from a live run performed by the audit itself. Applied.

None of these are taxonomy or scoring-model changes. Combined with the first pilot's four corrections, Phase 3 has now produced nine concrete, evidence-backed toolchain-invocation fixes across two structurally different stacks — a solid basis to check the remaining Phase 3 box ("Confirm Quality Framework v1.0 as the reference for the first global audit") once these corrections are folded in.
