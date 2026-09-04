# Toolchain — Phase 1

> Status: in progress. Each domain is smoke-tested (ephemeral install, quick run against an in-scope repo, license check) and validated before moving to the next, per the master prompt §9-10.
> Install strategy: ephemeral only (`uvx`, `npx`/`pnpm dlx`, native `npm`/`pnpm`/`composer` subcommands, or Docker for Go-only binaries with no package-manager wrapper) — see [`docs/adr/0004-toolchain-installation-strategy.md`](adr/0004-toolchain-installation-strategy.md).
> **npx safety rule (found 2026-08-26, see Architecture/dependencies below):** npm lets a package publish a CLI binary under any name, independent of the package name — `npx <bin-name>` resolves by *bin name*, which is a dependency-confusion vector if an unrelated (or malicious) package happens to claim that same bin name in the registry. Always invoke as `npx --package=<exact-npm-package-name> -- <bin-name>`, never bare `npx <bin-name>`, for every ephemeral npx-based tool in this document, including ones already validated above before this rule was found (`tsc`, whose package is `typescript`, not `tsc`).

---

## Security

| Tool | Availability | License | Verdict |
|---|---|---|---|
| Semgrep | `uvx semgrep` — works directly, clean JSON output | LGPL 2.1 | **Keep** |
| Gitleaks | No `npx`/`uvx` wrapper (Go binary) — via Docker `zricethezav/gitleaks` | MIT | **Keep**, with a required config decision (below) |
| Trivy (filesystem scan) | No `npx`/`uvx` wrapper — via Docker `aquasec/trivy` | Apache 2.0 | **Keep** |
| pip-audit | `uvx pip-audit -r requirements.txt` fails: uv-managed Python builds ship without `ensurepip`, so the tool's internal ephemeral venv creation crashes. Workaround: `uvx --python /usr/bin/python3.13 pip-audit ...` (forces the system Python, which has `ensurepip`) | Apache 2.0 | **Keep**, with the `--python` workaround documented as required config |
| `pnpm audit` | Native (pnpm already present), works directly, JSON | part of pnpm | **Keep** |
| `composer audit` | Native (composer already present), works directly, JSON | part of Composer | **Keep** |
| Semgrep, authN/authZ ruleset (category 4.6a gap) | Not evaluated yet — same `uvx semgrep` binary already validated above, with registry rulesets targeting auth misconfigurations (`p/security-audit` and framework-specific packs) | LGPL 2.1 | **Keep as candidate**, not smoke-tested. Coverage likely uneven across the portfolio's actual frameworks (FastAPI, Laravel, Vue/Node) — to verify per-stack at smoke-test |
| mdn-http-observatory (category 4.6b gap) | Not evaluated yet — npm-installable, `mdn-http-observatory-scan <url>` against a running server, produces a graded score (CSP, HSTS, X-Frame-Options, cookies, CORS, etc.), translatable onto the 0/2/4/6/8/10 anchored scale | MPL-2.0 (to confirm at smoke-test) | **Keep as candidate**, not smoke-tested. Needs a running server, same precondition class as Lighthouse/Playwright. Fallback candidate: `shcheck` (MIT, `santoru/shcheck`), lighter but less authoritative (presence-only check, no graded methodology) |

**Config decision (validated 2026-08-26):** Gitleaks must scan **tracked Git history** (default mode), never `--no-git` raw filesystem scanning. Smoke-tested against JobFlow: a raw filesystem scan flagged real credential files (`token.json`, `credentials.json`, etc.) as "leaks" even though they are correctly gitignored and never committed — a filesystem-mode scan produces false positives on legitimately untracked local secrets. Scanning Git history avoids this entirely, since it only sees what was actually committed.

---

## Dependency freshness (category 11)

Distinct from the Security domain's CVE-based audits above: these tools flag dependencies that are outdated but not necessarily vulnerable (no CVE filed). Detailed category-11 criteria are still deferred to Phase 2 (see [`docs/adr/0005-taxonomy-adjustments-deferred.md`](adr/0005-taxonomy-adjustments-deferred.md)); this is only the toolchain candidate list.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| `pip list --outdated` | Native (part of pip), run inside an ephemeral venv — see config decision below | MIT (pip) | **Keep**, with the lock-file caveat below |
| `npm outdated` / `pnpm outdated` | Native (npm/pnpm already present) — `npm outdated --json` smoke-tested on GeoChallenge-Tracker, `pnpm outdated --format json` on HiveMind, both clean structured output | part of npm/pnpm | **Keep** |
| `composer outdated` | Native (composer already present) — `composer outdated --format=json` smoke-tested on Summit-Stats, clean output, bonus `release-age`/`abandoned`/`latest-status` fields | part of Composer | **Keep** |

**Config decision (2026-08-26, see [`docs/adr/0012-registry-network-access-dependency-freshness.md`](adr/0012-registry-network-access-dependency-freshness.md)):** all three require a network call to a public package registry (PyPI, npm, Packagist) to know the latest available version. Gated behind the same opt-in-per-run mechanism as GitHub API access ([0003](adr/0003-github-api-network-access.md)), read-only, not enabled by default.

**License compliance (category 11.2 gap, researched 2026-08-26) — unlike freshness above, none of these three need a network call**, since license metadata is already present in the target's own installed/locked packages — not gated behind D15/D6.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| `pip-licenses` | Not evaluated yet — likely `uvx pip-licenses --format=json`, but needs the target's dependencies actually installed to enumerate their license metadata, same ephemeral-venv precondition as `pip list --outdated` (`uv export` + `uv pip install --python <scratch-venv>`) | MIT | **Keep as candidate**, not smoke-tested. Original tool, confirmed actively maintained again in 2026 (new maintainer, PEP 639 alignment work) — preferred over the `pip-licenses-cli` fork since the original is no longer the unmaintained one it once was |
| `license-checker-evergreen` | Not evaluated yet — likely `npx --package=license-checker-evergreen -- license-checker-evergreen --json`, reads `node_modules` package metadata directly, no network call | Same license as upstream `license-checker` (BSD-3-Clause family, to confirm at smoke-test) | **Keep as candidate**, not smoke-tested. Original `license-checker` (davglass) unmaintained since 2019; this fork is explicitly positioned as the actively-maintained drop-in replacement, preferred over `license-checker-rseidelsohn` (maintainer self-describes it as under-maintained) |
| `composer licenses --format=json` | Native (composer already present, same tool already validated for `composer audit`/`composer outdated`) — no new dependency at all | part of Composer | **Keep**, no smoke-test risk, reuses an already-validated native command |

**`pip list --outdated` needs an ephemeral resolved environment, not just the requirements file (smoke-tested 2026-08-26):**
- Unlike the other two, `pip list --outdated` only reports on an *installed* environment — there's no way to check a `requirements.txt`/lock file directly against PyPI without installing it somewhere first.
- Correct ephemeral pattern (consistent with D7): `uv export --frozen --no-hashes -o <scratch>/reqs.txt` (read-only export from the target's own `uv.lock`) → `uv pip install --python <scratch-venv> -r <scratch>/reqs.txt` → `uv pip list --python <scratch-venv> --outdated`. Verified on Triton (has `uv.lock`): correctly reports pinned-vs-latest for all 70 packages.
- **Pitfall found and avoided:** `uv sync --python <scratch-venv>` does **not** honor `--python` the way `uv pip install` does — it installs into the *target repo's own* `.venv` regardless (would have written into Triton if no `.venv` existed there yet). Do not use `uv sync` for this check; use `uv export` + `uv pip install --python` instead, which stays entirely inside the scratch venv.
- **Limitation:** this check is only meaningful for repos with a real lock file (`uv.lock`, `poetry.lock`, or `requirements.txt` with exact `==` pins). Smoke-tested on JobFlow (loose `>=` constraints, no lock file): an ephemeral `uv pip install` from `requirements.txt` always resolves to the latest version satisfying the constraint, so `pip list --outdated` on that fresh install is trivially empty — there is nothing pinned to compare against the registry. For unpinned repos, this criterion should report `N/A` rather than a false "up to date".

---

## Python

| Tool | Availability | License | Verdict |
|---|---|---|---|
| Ruff | `uvx ruff check --output-format=json` — works directly | MIT | **Keep** |
| mypy | `uvx mypy --ignore-missing-imports` — works directly **only when the target has no mypy plugin configured**. Smoke-tested on GeoChallenge-Tracker (Phase 3 pilot, 2026-08-26): fails outright (`Error importing plugin "pydantic.mypy": No module named 'pydantic'`) because its `pyproject.toml` declares the `pydantic.mypy` plugin — mypy needed the target's own runtime deps installed (`uvx --with-requirements requirements.txt --with mypy mypy ...`, same ephemeral pattern as pytest) to resolve it | MIT | **Keep**, with a detection rule: check `pyproject.toml`/`mypy.ini` for a `plugins = [...]` entry first; if present, run with `--with-requirements`, not bare `uvx mypy` |
| pytest | `uvx --with-requirements requirements.txt pytest ...` — works, correctly collects/runs the target repo's own tests | MIT | **Keep**, with a noted distinction below |
| coverage | `uvx coverage` — works directly | Apache 2.0 | **Keep** |
| radon (complexity) | `uvx radon cc --json` — works directly, structured cyclomatic-complexity output with rank | MIT | **Keep** |
| vulture (dead code) | Not evaluated yet — likely `uvx vulture <path>`, same ephemeral pattern as radon | MIT | **Keep as candidate**, not smoke-tested; actively maintained (2026 releases), reports a per-finding confidence (60-100%) worth surfacing as-is rather than smoothed away, per its own documented static-analysis limitation (may miss implicitly-called code) |
| docvet (docstring coverage, category 5.3 gap) | Not evaluated yet — likely `uvx docvet <path>`, same ephemeral pattern | MIT | **Keep as candidate**, not smoke-tested. Preferred over `interrogate` (older, more established, but a competing 2026 tool explicitly claims it's unmaintained — to verify directly against `econchick/interrogate`'s recent commit activity before trusting either). docvet is newer/less proven but actively released in 2026 and covers presence + staleness (git-diff/blame) rather than presence alone |

**Noted distinction:** unlike Ruff/mypy (pure static analysis, need only the target's source), pytest/coverage need the target repo's **own runtime dependencies installed** to actually execute its test suite — that's unavoidable, not a D7 violation. D7 only pins the *audit tool's own* version; the target's dependency versions for running its tests come from its own lockfile/`requirements.txt`, exactly as intended. Ephemeral install of those deps works via `uvx --with-requirements <file> pytest ...`.

**Cross-language rule — never trust a committed coverage artifact (Summit-Stats, second pilot, 2026-08-27):** a committed `coverage.xml` in Summit-Stats' repo root showed 73.97% statement coverage, below the repo's own 80% CI gate — a real-looking finding. Re-running `vendor/bin/pest --coverage` fresh produced 91.4%; the committed file was simply stale, not regenerated since an earlier point in the repo's history. This applies to any language/tool that can produce a coverage report (`coverage.xml` here, but equally `coverage-summary.json` for Vitest/Jest, `.coverage` for Python's `coverage.py`): the 3.1/3.4 coverage evidence must always come from a **live test run performed by the audit itself**, never from reading a checked-in report file, even when one is present and looks plausible.

---

## JavaScript / TypeScript

Smoke-tested on GeoChallenge-Tracker (Vue 3 + TS, `node_modules` already installed locally).

| Tool | Availability | License | Verdict |
|---|---|---|---|
| ESLint | `npx eslint . --format json` — resolves to the repo's own local ESLint binary/config (`node_modules/.bin/eslint`), clean JSON output. **Scope caveat found at Phase 3 pilot (GeoChallenge-Tracker, 2026-08-26):** a bare `.` at the repo root picked up `backend/.venv/lib/.../coverage_html.js` and `backend/htmlcov/coverage_html_cb_*.js` (gitignored, generated Python-toolchain artifacts, not source) as 42 false-positive errors, because the repo's own `eslint.config.js` only ignores paths its own `npm run lint` script actually scans (`frontend/src frontend/tests`), not the whole tree — same class of pitfall as the Dockerfile discovery issue below | MIT | **Keep**, but invoke with the repo's own `lint` script path scope (read `package.json`'s `scripts.lint` target), not a bare `.` |
| `tsc --noEmit` | `npx tsc --noEmit` — works, exit code 0/non-zero, no native JSON reporter (text output, `file(line,col): error TSxxxx: message` format, needs text parsing) | Apache-2.0 | **Keep** |
| knip (dead dependencies/exports) | `npx knip --reporter json` — ephemeral download via npx, clean JSON `issues` array. **Two caveats found at Phase 3 pilot (GeoChallenge-Tracker, 2026-08-26):** (1) without an `entry`/`project` config, knip flagged the real Vue entry points (`App.vue`, `main.ts`) as unused `files` — a known false-positive mode for unconfigured projects; (2) stdout was polluted by the target's own `console.log` side effects (from `playwright.config.ts`, evaluated during knip's config discovery) printed *before* the JSON payload — parsing must locate the first `{"issues"` prefix rather than `json.loads(stdout)` directly | ISC | **Keep**, with an audit-owned minimal `knip.json` (`entry`/`project` globs) per Vite-based repo, and defensive JSON-payload extraction from stdout |
| Vitest | `npx vitest run --reporter=json` — works, correctly collects/runs the target repo's own test suite (419/419 passed on GeoChallenge-Tracker), clean JSON | MIT | **Keep**, same runtime-dependency distinction as pytest/coverage above |
| Playwright | Present as `test:e2e` script, needs `build:test` + a running server + installed browsers first — heavier and more stateful than a static audit tool | Apache-2.0 | **Keep as candidate**, not smoke-tested this session; invocation strategy (build step, ephemeral server, headless-only) deferred to Phase 2 criterion definition |

**Note on ESLint config respect:** per the candidate-list intent (`docs/system-design.md#12`), ESLint runs with the target repo's **own** config as *input data*, not overridden by the audit system — the audit measures whether the repo's own linter (whatever rules it declares) passes, not whether it matches some external house style.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| ESLint `complexity` rule, audit-owned config (cyclomatic complexity, category 2.3/5.1/15.2 gap) | Not evaluated yet — same ESLint binary already validated above, invoked with an **audit-authored** config (`--no-eslintrc -c <audit-config>`) enabling only the `complexity` rule, independent of the repo's own `.eslintrc` | MIT (ESLint) | **Keep as candidate**, not smoke-tested. Deliberately not the target's own config here (unlike 2.1/2.2 above) — same "audit-owned, config-independent" logic already applied to radon for Python, so a repo can't inflate its complexity score just by not configuring the rule. Rejected alternative: dedicated npm packages (e.g. `cyclomatic-complexity`) are newer, less established, license not confirmed — reusing the already-validated ESLint binary is lower-risk |

| Spectral (OpenAPI contract linting, category 10.2 gap) | Not evaluated yet — `npx --package=@stoplight/spectral-cli -- spectral lint <spec-file> --format json`, built-in `spectral:oas` ruleset covers OpenAPI v2/v3 | Apache 2.0 | **Keep as candidate**, not smoke-tested. Precondition is lighter than Lighthouse/mdn-http-observatory: needs an already-exported OpenAPI spec file (FastAPI: call `app.openapi()`, needs the target's own runtime deps installed, same precondition class as pytest; Laravel: an artisan generation command via L5-Swagger), not a running server |

**Docstring coverage (category 5.3 gap): no candidate found for JS/TS.** Existing "coverage" tools in this ecosystem (`type-coverage`, `typescript-coverage-report`) measure TypeScript *type* coverage, not JSDoc *comment presence* — a different metric, not a substitute. Stays an open gap, not a pending-smoke-test candidate.

---

## PHP

Smoke-tested on Summit-Stats (Laravel + Pint + Pest, the portfolio's only in-scope PHP repo).

| Tool | Availability | License | Verdict |
|---|---|---|---|
| PHPStan (+ Larastan for Laravel targets) | **Not** an ephemeral/D7-style install for Laravel targets — see the resolved config decision below, a confirmed exception to D7 | MIT | **Keep**, config decision resolved below |
| Laravel Pint | Native (already a Summit-Stats devDependency) — `vendor/bin/pint --test --format=json` → clean `{"result":"pass"}` | MIT | **Keep** |
| Pest (built on PHPUnit) | Native (already a Summit-Stats devDependency) — `vendor/bin/pest --testsuite=Unit --log-junit=<file>` → 71/71 passed, standard JUnit XML (no native JSON reporter, same text/XML-parsing situation as `tsc`) | MIT (Pest) / BSD-3-Clause (PHPUnit) | **Keep** |
| PHPMD (complexity + dead code, category 2.3/5.1/15.2 gap) | Smoke-tested on Summit-Stats (second pilot, 2026-08-27), ephemeral isolated Composer install (own scratch project, see caution below), `vendor/bin/phpmd <path> xml codesize,unusedcode` (the `json` reporter doesn't exist — PHPMD only supports `xml`/`text`/`html`) → 3 real findings: 1 method exactly at the cyclomatic-complexity-10 threshold, 1 class at complexity 54 vs. a 50 threshold, 1 unused local variable. Signal-to-noise was good, no false positives found | BSD | **Keep**, validated |
| php-censor/phpdoc-checker (docblock coverage, category 5.3 gap) | Not evaluated yet — likely ephemeral isolated Composer install (same pattern as PHPStan), `vendor/bin/phpdoc-checker` with JSON output | BSD-2-Clause | **Keep as candidate**, not smoke-tested. Fork of the original `dancryer/php-docblock-checker`, checks classes/methods for docblock presence |

**Config decision resolved (Summit-Stats, second pilot, 2026-08-27):** PHPStan at default level 5 with no Laravel-aware extension raised 87 findings on Summit-Stats' `app/`, the bulk being false positives on Eloquent magic properties/methods and Laravel global helpers (`Function config not found`, `Access to an undefined property App\Models\Activity::$id`) that PHPStan can't resolve without Laravel's dynamic model metadata and helper stubs. The fix is `larastan/larastan`, but it **cannot** be installed the same way as plain PHPStan (D7's fully-isolated ephemeral scratch project): doing so fails outright with `Undefined constant "Larastan\Larastan\LARAVEL_VERSION"`, because Larastan resolves the target's Laravel version and loads its stub set by introspecting the app's *own* installed `vendor/`/`composer.lock` — an unrelated scratch Composer project has no such context to introspect, no matter what path is passed to `--paths`.

This is **not** a matter of scan scope — excluding `vendor/`/framework folders from the `paths` analyzed doesn't touch it, because the failure happens at Larastan's `extension.neon` config-parse time, before any file is even selected for analysis. The only working fix, confirmed by direct test: temporarily add `larastan/larastan` as a `require-dev` inside the **target repo's own** `composer.json` (`composer require --dev phpstan/phpstan larastan/larastan --no-interaction`), run `vendor/bin/phpstan` from there with an `extension.neon` include, then revert `composer.json`/`composer.lock` and re-run `composer install` to restore the repo to its original state. Confirmed result on Summit-Stats: 87 file_errors of mostly noise dropped to 12 file_errors of real signal (an unused class constant, generic-type mismatches on Eloquent relation return types, a potential null-safe-call issue, by-reference parameter warnings). This is a genuine, documented exception to D7's "audit tool is always independent of the target's own tooling" rule — Laravel-aware static analysis structurally requires running inside the target's dependency tree. Any future orchestration must revert the target's `composer.json`/`composer.lock` afterward so the audit never leaves a footprint in the scanned repo.

**Isolated-scratch-per-tool rule (Summit-Stats, second pilot, 2026-08-27):** for tools that genuinely can stay in a D7-style ephemeral scratch project (PHPMD, and plain non-Laravel PHPStan), each tool needs its **own** scratch Composer project — never share one `vendor/` across multiple ephemeral PHP tools. Installing PHPMD into a scratch dir that already had PHPStan+Larastan caused a fatal Composer dependency conflict (`PDepend\DependencyInjection\PdependExtension::load(...)` incompatible with the Symfony DI version Larastan's tree pulled in) — not a PHPMD bug, a transitive clash between two unrelated tools' dependency trees sharing one `vendor/`. A fresh, PHPMD-only scratch project resolved cleanly.

**Note on Pint/Pest native install:** unlike PHPStan (audit-system-owned, ephemeral, independent of the target), Pint and Pest here are the target repo's **own** pinned devDependencies, run natively via `vendor/bin/`, the same pattern already validated for `composer audit`/`composer outdated`. This is intentional, not an inconsistency: style/test tools measure *the repo's own configured behavior*, the same reasoning already applied to ESLint above — whereas PHPStan (and Ruff/mypy) are pure external static analysis, run at an audit-system-controlled version so score stability (D7) isn't at the mercy of whether the target repo bothers to pin/update its own linter.

---

## Code duplication (category 2.5 gap, cross-language)

Unlike the complexity/dead-code gaps above (separate tool per language), a single candidate covers the whole portfolio's language mix.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| jscpd | Not evaluated yet — likely `npx --package=jscpd -- jscpd <path> --reporters json` (v4, Node-based) or a prebuilt v5 Rust binary (no Node runtime needed) | MIT (to confirm at smoke-test) | **Keep as candidate**, not smoke-tested. Single tool for Python/JS-TS/PHP/Vue (223+ languages via Prism grammars), widely adopted (Microsoft, Salesforce, bundled in super-linter/Codacy), actively developed in 2026 (v5 Rust rewrite, 24-37x faster than v4). Rejected alternative: PMD-CPD also covers Python/PHP/JS, but needs a JVM runtime — an extra dependency class no other tool in this toolchain requires (uvx/npx/composer/Docker only), with no clear advantage over jscpd for this portfolio's languages |

---

## Architecture / dependencies (category 11 sub-scope: cycles, layering)

| Tool | Availability | License | Verdict |
|---|---|---|---|
| madge (JS/TS, originally proposed) | `npx --package=madge -- madge --extensions ts --json <dir>` — works cleanly on a pure-TS subtree (`frontend/src/utils` on GeoChallenge-Tracker), but **hard-fails** with a parser crash as soon as the scanned tree includes a `.vue` SFC (confirmed on `frontend/src`) | MIT | **Reject** — no native Vue SFC support, and all three JS/TS repos in scope (GeoChallenge-Tracker, HexaRot, HiveMind) are Vue-based |
| dependency-cruiser (replacement) | `npx --package=dependency-cruiser -- depcruise --no-config --include-only "^frontend/src" --output-type json <dir>` — works cleanly across the full tree, correctly recognizes `.vue` SFCs as graph nodes (26/109 modules on GeoChallenge-Tracker), reports `circular`/`orphan` per module | MIT | **Keep**, replaces madge for the JS/TS side |
| pydeps (Python) | `uvx pydeps <package> --show-deps --no-output --max-bacon=0` (or `--show-cycles`) — works directly, structured JSON, tested on Triton's `engine` package | Apache 2.0 | **Keep** |
| import-linter (Python) | `uvx import-linter` — runs, but it's a **rules-enforcement** tool, not a generic cycle detector: it does nothing without a target-authored `.importlinter`/`setup.cfg` config declaring architectural "contracts" (layers). None of the in-scope Python repos (Triton, JobFlow, Stamped) define one | Apache 2.0 | **Reject** for the generic portfolio toolchain — nothing to evaluate without repo-authored config; revisit per-repo only if one adds a contract file later |
| deptrac (PHP) | Ephemeral install via isolated Composer project (same pattern as PHPStan) — `deptrac analyse` requires a target-authored `deptrac.yaml`/`depfile.yaml` declaring layers. Summit-Stats has none; confirmed via `CannotLoadConfiguration` error | MIT | **Reject** for the generic portfolio toolchain, same rationale as import-linter |

**Near-miss found during this smoke test:** `npx depcruise` (bare bin name) almost resolved to an unrelated npm package literally named `depcruise` — confirmed via `npm view depcruise` to be a registered *dependency-confusion placeholder* (`🚫 Placeholder to prevent dependency confusion`, published specifically to squat the bin name ahead of bad actors), not the real `dependency-cruiser` tool. No harm done here since the placeholder is inert, but it demonstrates the risk described in the npx safety rule at the top of this document was live, not theoretical. All ephemeral `npx` invocations in this document (past and future) must use `--package=<exact-name> --`.

**Pattern for import-linter/deptrac going forward:** both tools are legitimate and worth re-offering as an *opt-in* criterion in Phase 2 — e.g. "if this repo defines its own architectural contract file, is it being respected?" — rather than a portfolio-wide generic check, since authoring the contract itself is a repo-specific design decision the audit system shouldn't make on the developer's behalf.

---

## Containers

Both tools are Go/Haskell binaries with no `uvx`/`npx` wrapper — run via Docker, per D7.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| Hadolint (Dockerfile lint) | `docker run --rm -i hadolint/hadolint hadolint --format json - < Dockerfile` — smoke-tested on GeoChallenge-Tracker's `backend/Dockerfile`, 3 plausible low-noise findings (unpinned `apt-get`/`pip` versions, missing `--no-cache-dir`) | **GPL-3.0** | **Keep**, license note below |
| Trivy (image scan) | `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --format json --severity HIGH,CRITICAL --scanners vuln <image>` — smoke-tested against the already-built local image `geochallenge-tracker-backend:latest`, found 194 Debian OS-package + 7 Python-package HIGH/CRITICAL CVEs, plausible | Apache 2.0 | **Keep**, requires access to the local Docker daemon socket |

**License note:** Hadolint is GPL-3.0, stricter (copyleft) than every other tool validated so far (MIT/Apache/BSD/ISC). Not a concern here: the audit system only *invokes* Hadolint as an external subprocess via its own Docker image, it never links or embeds Hadolint's code into the audit system's own codebase, so GPL's copyleft/distribution clauses don't attach. No different in principle from calling any other CLI tool.

**Image-scan precondition:** unlike Hadolint (works on the Dockerfile source, always available), `trivy image` needs an already-**built** image. It was tested here against an image already present from prior local `docker compose` usage — the audit system does **not** build images itself as a side effect of scanning (that would be a heavier, more invasive step than a static/config-only audit tool should take). If a repo has no locally built image at audit time, this check should report `N/A` rather than triggering a build.

**Dockerfile/compose discovery pitfall found (2026-08-26):** naive `find . -iname Dockerfile*` on Summit-Stats surfaced 9 Dockerfiles, most of them noise: `vendor/laravel/sail/runtimes/*/Dockerfile` (third-party package internals, not the repo's own infra) and duplicates under `.claude/worktrees/*/vendor/...` (a stale worktree copy). Discovery must exclude `vendor/`, `node_modules/`, and any `.git`-worktree-style nested directory — scanning only the repo's own top-level/service Dockerfiles, not vendored or duplicated copies.

**Generalized to a portfolio-wide orchestration rule (second pilot, Summit-Stats, 2026-08-27):** the same `.claude/worktrees/` directory independently broke two more tools on this repo, confirming the pitfall above isn't Dockerfile-specific: (1) Vitest's default `test.exclude` covers `node_modules/**` and `e2e/**` at the repo root but not a nested worktree copy of the same paths, silently double-counting every test (62 real → 124 reported); worse, `npm run test:coverage` (no path filter) **hard-failed** with `Playwright Test did not expect test.describe() to be called here` because Vitest picked up a Playwright spec file duplicated inside the worktree — a full run failure, not just noisy counts; (2) Trivy's filesystem scan (`trivy fs`) double-counted CVEs from `composer.lock`/`package-lock.json` duplicated inside the worktree.

**This is directly filterable per tool — no manual/skip-tool fallback needed.** Every tool in this toolchain that recursively walks the filesystem has a native exclusion mechanism, confirmed by checking each one's own CLI: `find` (`-not -path '*/pattern/*'`), Vitest (`--exclude <glob>`), `trivy fs`/`trivy image` (`--skip-dirs`), dependency-cruiser (`-x/--exclude <regex>`), ESLint (`--ignore-pattern`), PHPMD (`--exclude`, comma-separated glob patterns), PHPStan (`parameters.excludePaths` in its neon config — no CLI flag, but trivial to add to the config the audit already generates). **The exclude pattern should not be hardcoded to `.claude/worktrees`** — that's just where this specific pilot's worktrees happened to live. The correct, general implementation is to run `git worktree list --porcelain` against the target repo first, extract every worktree path except the main one, and feed those paths into whichever exclusion mechanism the tool being invoked supports. This is a pure orchestration fix (compute the exclude list once per repo, pass it to every recursive tool call) — Phase 4 should implement it as a shared step, not per-tool special-casing.

---

## Performance (frontend only — category 6, see `docs/quality-framework.md`§4.6)

Backend/DB performance is deliberately excluded from Quality Framework v1.0 (no objective definition without a per-project SLA) — not a toolchain gap, no candidate evaluated here. Frontend has one plausible candidate, listed for Phase-2-triggered validation, not yet smoke-tested this session.

| Tool | Availability | License | Verdict |
|---|---|---|---|
| Lighthouse | Not evaluated yet — likely `npx --package=lighthouse -- lighthouse <url> --output json`, same class of precondition as Playwright (needs a running server, a build step, headless Chrome) | Apache 2.0 | **Keep as candidate**, not smoke-tested; known open doubts (reproducibility of the score run-to-run, narrow load-time-only scope) carried in `quality-framework.md`§4.6, to revisit before this criterion is trusted at more than MEDIUM confidence |

---

## Git / CI

| Tool | Availability | License | Verdict |
|---|---|---|---|
| actionlint | No `uvx`/`npx` wrapper (Go binary) — via Docker: `docker run --rm -v <repo>:/repo -w /repo rhysd/actionlint:latest -format '{{json .}}'` — auto-discovers `.github/workflows/` with no path argument needed, smoke-tested on GeoChallenge-Tracker, 2 real findings (embedded `shellcheck` issue: unquoted variable enabling globbing/word-splitting in a `run:` step) | MIT | **Keep** |
| Branch protection / PR review requirements / Actions run history | Not local-`.git`-derivable — needs the GitHub API | — | Deferred to D6 (opt-in, read-only GitHub API access), not part of the local static toolchain |

**Bonus found:** actionlint bundles `shellcheck` analysis for inline `run:` shell scripts inside workflow steps, so a single tool catches both YAML-workflow-syntax issues and shell-scripting issues in the embedded scripts, without needing a separate shellcheck invocation.

---

## Pre-commit hooks (feeds the D12 criterion: coverage matrix)

Not a single "run and get findings" tool — D12 needs the coverage-**content** (which validator types cover which domains), not just presence/absence of a hook framework. Smoke-tested by reading real configs across the in-scope repos that use each framework: `.pre-commit-config.yaml` (5 repos: CC-Beacon, GeoChallenge-Tracker, JobFlow, Stamped, Triton) and `.husky/` (3 repos: HexaRot, HiveMind, Summit-Stats). No in-scope repo uses `lefthook.yml`.

| Framework | Evidence extraction | Verdict |
|---|---|---|
| `pre-commit` (Python ecosystem) | Config is fully declarative in `.pre-commit-config.yaml` — each hook's `id`/`name` and `files` regex directly give (validator type, domain) pairs. `uvx pre-commit validate-config` confirms the file is schema-valid (exit 0 on GeoChallenge-Tracker) as a cheap sanity check before parsing | **Keep** — YAML parsing alone is sufficient, no need to actually execute the hooks |
| `husky` | **Not self-contained.** `.husky/pre-commit` is typically a one-line shell wrapper (`npx lint-staged` on both HexaRot and Summit-Stats) — it names *no* validator itself. The real (validator type × domain) matrix lives one hop away, in `package.json`'s `"lint-staged"` key (glob pattern → command list per pattern) | **Keep**, but extraction **must chain two files**: `.husky/<hook-name>` → confirm it delegates to `lint-staged` → then read `package.json`'s `lint-staged` key for the actual matrix. Reading `.husky/` alone gives a false "covered" or "empty" signal |
| `lefthook` | No in-scope repo uses it — config format (`lefthook.yml`) is declarative YAML like `pre-commit`, so the same direct-parsing approach should apply, but this is **unverified**, not smoke-tested | **Keep as candidate**, verify against a real config if/when one appears in scope |

**Concrete coverage-matrix results found (useful as worked examples for the D12 criterion definition in Phase 2):**
- GeoChallenge-Tracker (`.pre-commit-config.yaml`): backend gets ruff (lint) + ruff-format (format) + mypy (type-check); frontend gets prettier (format) + eslint (lint) + vue-tsc (type-check) — full matrix, all 6 applicable cells covered.
- HexaRot (husky → lint-staged): backend and frontend both get eslint (lint) only — no format or type-check hook on either domain, 2/6 cells covered.
- Summit-Stats (husky → lint-staged): frontend gets eslint (lint) + prettier (format); PHP backend gets Pint (format only, no PHPStan wired into the hook) — 3/6 cells covered (using the 3-validator-type model; Pint straddles lint/format in practice for PHP, worth a definitional note in Phase 2).

---
