# Phase 3 pilot audit — GeoChallenge-Tracker

> Manual run, 2026-08-26. The orchestration/dashboard system doesn't exist yet (that's Phase 4) — this is a hand-run pass of the **validated** tools from `docs/toolchain.md` against GeoChallenge-Tracker, scored by hand against the archetypes and model in `docs/quality-framework.md`, to calibrate the framework before it's implemented. Candidate tools flagged "not smoke-tested" in `toolchain.md` were deliberately **not** run here — they're still gaps regardless of pilot results, per `quality-framework.md`§5. Raw tool outputs live in the session scratchpad, not committed (ephemeral, reproducible on demand); this document is the durable record.

---

## 1. What was run

| Domain | Tools | Result |
|---|---|---|
| Security | Semgrep, Gitleaks, Trivy (fs), pip-audit | 2 Semgrep WARNING, 6 Gitleaks findings (all false positives, see §3), 3 Trivy CVEs + 4 misconfigs, 1 pip-audit CVE (already suppressed in CI with a documented justification) |
| Python | Ruff, mypy, radon, pytest+coverage | Ruff clean, mypy clean (after fix, see §3), radon: 618 blocks (2×F, 13×D), 1291/1291 unit tests passed |
| JS/TS | ESLint, tsc, knip, Vitest | ESLint 42 errors (all false positives, see §3), tsc clean, knip 39 dead-code issues (2 false positives, see §3), 419/419 Vitest tests passed |
| Architecture | dependency-cruiser, pydeps | 0 circular/orphan violations (frontend), backend graph resolved cleanly (126 modules) |
| Containers | Hadolint, Trivy (image) | 3 Hadolint findings (backend Dockerfile), 201 backend-image CVEs (188 HIGH/13 CRITICAL), 60 frontend-image CVEs (56 HIGH/4 CRITICAL) |
| Git/CI | actionlint | 2 findings (shellcheck, unquoted variable in `build-push.yml`) |
| Structural heuristics | D11/D12 evidence, README/DESIGN.md, OpenAPI, engines, TODO density | see §2 |

---

## 2. Category-by-category scoring

Only categories/criteria with direct evidence gathered this pass are scored. Criteria whose only candidate tool is "not smoke-tested" (per `toolchain.md`) stay `N/A`/gap, unchanged by this pilot. LLM-judgment criteria 1.4 and 3.5 were evaluated in a follow-up code-reading pass (no new tooling, see below); 10.1 still needs a rendered-UI pass (browser) not done in this CLI-only run — left unscored, flagged in §4.

### 1. Architecture & design
- 1.1 Dependency direction/circularity — **10** (0 cycles, both dependency-cruiser and pydeps clean)
- 1.2 Architectural documentation — **10** (`DESIGN.md`, 1897 words, substantive)
- 1.3 Module size distribution — not scored (JS/PHP tooling gap, per `toolchain.md`; Python side has radon data but no dedicated size-distribution threshold defined yet)
- 1.4 Architectural style consistency — **4** (visibly mixed, not a single dominant style: 5/15 backend route files follow a clean thin-controller/service-delegation pattern with typed `response_model` — `auth.py`, `meta.py`, `my_challenge_progress.py`, `my_challenge_tasks.py`, `zones.py`; core-domain routes instead build MongoDB queries directly in the route handler and return untyped dicts — `caches.py` (6/6 routes, 0 `response_model`), `caches_elevation.py`, `caches_geocoding.py`, `referentials.py`; several files mix both patterns in the same file — `my_challenges.py`, `my_challenge_targets.py`, `my_profile.py`. Frontend shows the same split: composables (`useXData`) are used in most pages, but several of those same pages also call `api.get()` directly for auxiliary data instead of going through a composable — e.g. `Calendar.vue`, `Details.vue`, `Matrix.vue`, `Tasks.vue`.)

### 2. Code quality
- 2.1 Linter clean pass rate — **10** (Ruff clean; ESLint's 42 errors are 100% false positives, see §3 — true pass rate on actual source is clean)
- 2.2 Type-checking pass — **10** (mypy clean, tsc clean)
- 2.3 Cyclomatic complexity — **6** (Python: 502 A / 72 B / 29 C / 13 D / 2 F blocks out of 618 — the great majority are fine, but 2 functions at F-rank, complexity 70 and 62, are real hotspots; JS/PHP still a tooling gap)
- 2.4 Pre-commit quality gate — **10** (D12: full 6/6 matrix covered — ruff lint+format+mypy backend, prettier+eslint+vue-tsc frontend, confirmed by reading `.pre-commit-config.yaml` directly)
- 2.5 Code duplication — not scored (jscpd candidate, not smoke-tested)

### 3. Testing & reliability
- 3.1 Unit tests present & passing, with coverage — **10** (1291/1291 backend, 419/419 frontend, both green; coverage % not extracted this pass but both suites are substantial and green)
- 3.4 CI executes the test suite — **10** (`ci.yml`: `backend-test` and `frontend-unit` jobs both run the real suites with coverage upload)
- 3.3 E2E tests — **5 (IN_PROGRESS)** (Playwright configured, `test:e2e` script present, but not wired into `ci.yml` — matches the Phase 1 smoke-test note exactly)
- 3.5 Test quality/relevance — **9** (sampled `test_dto_validation.py`, `test_calendar_verification.py` (backend) and `calendar-data.spec.ts` (frontend): assertions check precise computed values and real edge cases — leap-year day counts, duplicate-day dedup, completion-rate math, reactivity — not tautological truthy checks. Grep across the full suite found 0 backend `assert True`/bare-result patterns and only 4/598 frontend weak `toBeTruthy()`/`not.toThrow()` expectations out of 1861 backend and 598 frontend total assertions — meaningful assertions dominate. Caveat: 4 backend files — `_test_progress.py`, `_test_targets_smoke.py`, `_test_user_challenge_tasks_suite.py`, `_test_user_challenge_tasks_verbose.py`, 1228 lines total — are named with a leading underscore, so pytest never collects them; orphaned test code, cross-ref 15.2, doesn't affect the active suite's quality but is dead-code debt worth flagging separately)

### 4. Security
- 4.1 Dependency vulnerabilities — **6** (pip-audit: 1 CVE, already triaged and suppressed in CI with a documented, re-verified justification — `PYSEC-2026-1325`/ecdsa Minerva timing attack, not exploitable since the repo only signs JWTs with HS256; `npm audit` (not run in the first pass): 2 HIGH, both with a fix available — `flowbite-vue` transitive dep and `nanoid`, fix requires a major-version bump not yet applied)
- 4.2 Secrets in tracked history — **10** (0 real secrets; Gitleaks' 6 raw hits are the false-positive pattern in §3, none of which should trigger P1)
- 4.4 Container image vulnerabilities — **2 (uncapped: see below)** (backend image, Debian 13.6: 13 CRITICAL, 0 with a fix published yet — real but unactionable debt, doesn't trigger P2; frontend image, Alpine 3.23.3 + Node: **4 CRITICAL with a fix available and not applied** — `libcrypto3`, `libssl3`, `tar`, `esbuild`/stdlib — this is the concrete P2 trigger)
- 4.5 Dockerfile hardening — **6** (3 Hadolint warnings: unpinned `apt-get`/`pip`, missing `--no-cache-dir`; plus Trivy misconfig: both Dockerfiles run as root, no `HEALTHCHECK`)

**Critical penalty check (§3.2):** P1 does **not** trigger (0 real secrets, see §3). **P2 triggers**: the follow-up Trivy/fix-availability cross-check (flagged as open in the first pass) found 4 CRITICAL CVEs on the frontend image with a published fix not applied (rebuild against a patched Alpine + Node/esbuild base would clear them). Per `quality-framework.md`§3.2, category score is capped at **4** (uncapped average of the 4 scored criteria above: 6.0). This is a real confirmation of the P2 mechanism working as designed, not a theoretical clause.

### 7. DevOps / CI-CD
- 7.1 CI presence & health — **10** (5-job `ci.yml`, all green paths; actionlint clean apart from 2 minor shellcheck notes)
- 7.2 Reverse proxy / local-prod parity — **10** (D11: Traefik labels present and correctly differentiated in both `docker-compose.yml`, dev, plain HTTP and `docker-compose.prod.yml`, TLS + Let's Encrypt — textbook DONE)
- 7.4 Deployment automation — **10** (`build-push.yml`: builds and pushes both images to GHCR on merge)

### 8. Documentation
- 8.1 README completeness — **10** (setup/installation, architecture overview, features, screenshots — all present)
- 8.3 API documentation — **10** (FastAPI instantiated with no `docs_url` override → default Swagger/OpenAPI auto-docs active)

### 9. Observability / operations
- 9.1 Structured logging — **6** (`logging.getLogger(__name__)` used consistently across services — real logger, not bare `print`, but no structured/JSON formatter confirmed)
- 9.2 Error tracking integration — **0 (TODO)** (no Sentry or equivalent found in either `backend/requirements.txt` or `frontend/package.json`)
- 9.3 Health-check endpoint — **10** (`/health` route present, `HealthCheck` response model)

### 11. Dependency management
- 11.1 Dependency freshness — `N/A` this pass (D15 registry-lookup opt-in not exercised)
- 11.3 Dependency footprint — not scored (no portfolio baseline yet, per the criterion's own note)

### 12. Configuration management
- 12.2 Environment separation — **10** (`.env`, `.env.example`, `.env.test` all present and distinct)
- 12.3 Config validation at startup — **10** (`Settings(BaseSettings)` via `pydantic-settings`, confirmed in `backend/app/core/settings.py`)

### 13. Data quality
- 13.1 Schema/migration versioning — **0 (TODO)** (no migrations directory or schema-version mechanism found — a real gap for a MongoDB app with no ODM-level migration tool, not a tooling blind spot)
- 13.3 Test data/fixtures quality — **0 (TODO)** (no faker/factory pattern found in `backend/tests`; unlike Summit-Stats, tests appear to use inline literals)

### 14. Developer experience
- 14.1 Onboarding documentation — **10** (`CONTRIBUTING.md` present, README installation section is detailed)
- 14.3 Script/task standardization — **10** (`package.json` scripts cover dev/test/lint/build/typecheck; backend has an equivalent lifecycle via `requirements-dev.txt` + documented commands)

### 15. Technical debt
- 15.1 TODO/FIXME density — **~23 occurrences** across `backend/app` + `frontend/src` (raw count only, no KLOC normalization done this pass, no severity classification — the interpretive layer wasn't run)
- 15.3 Framework/runtime version currency — **10** (`engines.node` pinned to a real range, `>=20 <=24`)

---

## 3. Calibration findings — false positives and tool-invocation corrections

These are the actual value of Phase 3: places where the frozen framework or the validated toolchain needs a correction *before* Phase 4 builds automation around it.

### 3.1 Gitleaks: 6/6 findings are false positives on fake test tokens

All 6 hits are `generic-api-key` matches on lines like `fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"` in `backend/tests/test_auth.py` and `backend/tests/integration/test_endpoints_auth.py` — clearly-named test fixtures, not real secrets. This is exactly the scenario D14 (`human_verdict` feedback loop) was designed for, but it also suggests a **cheap pre-filter** worth adding to the P1 critical-penalty logic itself: a `generic-api-key` match inside a file path matching `tests?/` or `test_*`, on a variable named `fake_*`/`mock_*`/`dummy_*`, is a strong enough pattern to hold at `PENDING_CONFIRMATION` by default rather than trusting the raw Gitleaks count for the P1 cap. Recommend as a Phase 3 correction to `quality-framework.md`§3.2's P1 condition — not a framework redesign, a refinement of "confirmed" secret.

### 3.2 ESLint: naive `eslint .` at repo root picks up vendored/generated noise

Running `npx eslint .` from the repo root (rather than the repo's own `npm run lint` scope) picked up `backend/.venv/lib/.../coverage_html.js` and `backend/htmlcov/coverage_html_cb_*.js` — third-party/generated JS files that happen to exist locally (gitignored, never committed) but aren't part of the actual source tree. All 42 "errors" are noise from these two files; the real frontend source is clean. **Root cause:** the repo's own `eslint.config.js` only ignores `frontend/dist`/`frontend/coverage`/`node_modules` because its own lint script never scans outside `frontend/`; the audit tool broke that assumption by scanning `.` at the repo root. This is the same class of pitfall already documented for Dockerfile discovery (`toolchain.md`§Containers) and Gitleaks filesystem-mode (`toolchain.md`§Security). **Correction needed:** ESLint invocation must reuse the repo's own configured lint scope (read `package.json`'s `lint` script target) rather than defaulting to `.`, or at minimum exclude `.venv/`, `htmlcov/`, `__pycache__/` alongside `node_modules/`.

### 3.3 mypy needs the target's runtime deps installed, contradicting `toolchain.md`'s "pure static analysis" framing

`uvx mypy --ignore-missing-imports app` failed outright (`Error importing plugin "pydantic.mypy": No module named 'pydantic'`) because this repo's `pyproject.toml` declares the `pydantic.mypy` plugin. mypy had to be run as `uvx --with-requirements requirements.txt --with mypy mypy ...` instead — the same ephemeral-install pattern already used for pytest, not the "just the target's source" pattern `toolchain.md`'s JS/TS section implies for its pure-static tools. **Correction needed:** update `toolchain.md`'s Python section to note that mypy needs the target's own runtime deps installed whenever the repo configures a type-checking plugin (Pydantic, Django, SQLAlchemy, etc.) — not universally, but detectably (presence of `[tool.mypy] plugins = [...]` in `pyproject.toml`/`mypy.ini`).

### 3.4 knip flags real entry points as dead files without an `entry` config

`frontend/src/App.vue` and `frontend/src/main.ts` — the actual Vue app entry points — were flagged under `files` (unused) because the default `npx knip` invocation didn't declare an entry point via `knip.json`/`package.json#knip`. This is knip's own well-known false-positive mode for unconfigured projects. **Correction needed:** either author a minimal audit-owned `knip.json` (declaring `entry: ["frontend/src/main.ts"]`, `project: ["frontend/src/**"]`) reused across all Vite-based repos in the portfolio, or treat `App.vue`/`main.ts`/`index.ts` as an always-excluded entry-point pattern before counting knip's `files` issue type toward the 5.2 score.

### 3.5 knip's stdout gets polluted by the target's own config side effects

`npx knip --reporter json` printed `playwright.config.ts`'s dotenv-loading `console.log` output *before* the JSON payload, because knip evaluates config files (including `playwright.config.ts`, referenced from `vitest.config.ts`) during discovery. The raw stdout wasn't valid JSON until locating the `{"issues"` prefix and slicing from there. **Correction needed:** any future orchestration around knip must not assume clean stdout — locate the JSON payload defensively (first `{` that parses) rather than `json.loads(stdout)` directly. Worth a one-line note in `toolchain.md`'s JS/TS section.

---

## 4. Open items not resolved by this pass

- **10.1 (graphic design, D13)** — still not evaluated. Its factual layer (WCAG contrast, responsive breakpoints) needs the UI actually rendered — a browser pass, not just CLI tooling. 1.4 and 3.5 were resolved in a follow-up code-reading pass (no rendering needed, see §2) and no longer block Phase 3 sign-off; 10.1 is the one remaining interpretive gap.
- **4.1/4.4 critical-penalty cross-check (P2)** — resolved this pass: cross-referenced Trivy image scans (backend + frontend) and `npm audit` against fix availability. Result: P2 triggers on the frontend image (4 CRITICAL with a fix available), Security category capped at 4. See §2.
- **Category 6 (Performance)** — correctly out of scope for this pass: Lighthouse is an unvalidated candidate (stays a gap regardless of pilot results), backend/DB performance is deliberately excluded from v1.0 (`quality-framework.md`§4.6).
- **11.1 (dependency freshness)** — correctly `N/A`: D15 registry-lookup opt-in wasn't exercised this run, not a framework problem.

---

## 5. Recommended framework corrections (for `quality-framework.md`)

1. **§3.2 P1 condition** — add the test-fixture pre-filter described in §3.1 above, so an obvious fake-token pattern in a test file doesn't blindly trigger `PENDING_CONFIRMATION`-worth suspicion at the same weight as a real committed credential.
2. **`toolchain.md` mypy entry** — document the plugin-detection caveat from §3.3 (runtime deps needed when a mypy plugin is configured).
3. **`toolchain.md` ESLint entry** — document the scope caveat from §3.2 (reuse the repo's own lint script's path scope, don't default to `.`).
4. **`toolchain.md` knip entry** — document the entry-point config need (§3.4) and the stdout-parsing caveat (§3.5).

None of these are taxonomy, weight, or scoring-model changes — the framework's structure held up well against a real, fairly mature repo. All four corrections are toolchain-invocation precision fixes, exactly the kind of finding Phase 3 is meant to surface before Phase 4 hardens these invocations into automated orchestration.
