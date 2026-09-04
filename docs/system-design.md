# System Design — Phase 0

> **Historical archive.** This is the original Phase 0 design proposal,
> kept as-is for context. It has since been superseded by the
> implementation: see [`docs/architecture/`](architecture/) for the
> current per-component architecture, [`docs/quality-framework.md`](quality-framework.md)
> for the frozen methodology, and [`docs/roadmap.md`](roadmap.md) for
> current status. Not translated (archive, not reader-facing).

> Status: Phase 0 draft (architecture proposal, not implemented at the time of writing).
> Methodology reference: none yet at the time of writing — Quality Framework v1.0 is now frozen, see `docs/quality-framework.md`.

This document separates, as required by the master prompt, what was **observed**, what is **interpreted**, and what is **proposed**. It reflects the state of the project at Phase 0; items marked as requiring a decision were tracked in the now-relocated `docs/work-in-progress/open-decisions.md` and have since been resolved (see `docs/adr/`).

---

## 1. Local environment (OBSERVED)

Host: Linux, x86_64, 31 GiB RAM, 351 GB free on the working volume — no resource constraint for local static analysis or an SQLite-backed dashboard.

| Tool | Version | Notes |
|---|---|---|
| git | 2.47.3 | |
| docker / docker compose | 29.3.0 / v5.1.0 | |
| node / npm / pnpm | v23.1.0 / 11.6.1 / 10.4.1 | |
| python3 / pip | 3.13.5 / 25.1.1 | |
| php / composer | 8.5.3 / 2.9.5 | |
| sqlite3 | 3.46.1 | |
| npx / uvx / pipx | available | can run ephemeral tool versions without global install |

No analysis/security tool is installed globally: **ruff, mypy, eslint, phpstan, semgrep, gitleaks, trivy are all absent from the system PATH.** They exist today only where a given repository declares them as a dependency.

**Interpretation:** the toolchain strategy cannot assume a tool is present system-wide. It must either run tools ephemerally (`npx`, `uvx`, `pipx`, or containerized), or install a pinned, versioned toolchain dedicated to the audit system itself — kept separate from each audited repo's own tooling so the audit is not silently dependent on whatever a given repo happens to have configured. See `docs/open-decisions.md#d7`.

**Traefik as portfolio-wide reverse proxy (OBSERVED + DECIDED, 2026-08-25):** the developer runs Docker-based deployments for their projects and uses Traefik, both locally and remotely, to standardize local/prod parity across the portfolio ("reliable production behavior = professional behavior" for portfolio-quality projects). A `~/projets/traefik/` directory exists holding per-project routing configs (local + prod) for some repos — this directory is **not itself part of the audited portfolio** and is **not read by the audit system**; it is a convenience grouping for manual post-deployment comparison. The canonical Traefik configuration is expected to live inside each repository (docker-compose labels or a dedicated file), which keeps the "one repo = one filesystem root" assumption intact. See the new taxonomy criterion in §6 and `docs/open-decisions.md#d11`.

---

## 2. Repository inventory (OBSERVED)

20 local git repositories were found under `~/projets/`. This is a full inventory, kept for record — portfolio scope itself is now decided (see below and `docs/open-decisions.md#d1`).

| Repository | Last commit | Detected markers | Likely stack (interpretation) | Scope |
|---|---|---|---|---|
| CC-Beacon | 2026-08-04 | CI | FastAPI + web frontend (README-confirmed), ships with a VPS-facing `docker-compose.prod.yml` | **In scope** |
| GeoChallenge-Tracker | 2026-08-03 | package.json, docker-compose.yml, CI | FastAPI + MongoDB + Vue 3 (README-confirmed), has DESIGN.md/CONTRIBUTING/codecov | **In scope** |
| HexaRot | 2026-08-22 | package.json (monorepo), docker-compose.yml, CI | NestJS + Vue 3 + TypeScript (package.json-confirmed), backend/frontend workspaces | **In scope** |
| HiveMind | 2026-08-05 | package.json (pnpm workspace), docker-compose.yml, CI | Vue/TS monorepo, Playwright e2e (package.json-confirmed) | **In scope** |
| JobFlow | 2026-08-18 | requirements.txt, pyproject.toml | Python automation/CLI (Google API), ruff pre-configured. Not a web app. | **In scope** |
| Stamped | 2026-05-22 | pyproject.toml, CI | Python + FastAPI (pyproject-confirmed) | **In scope** |
| Summit-Stats | 2026-08-05 | package.json, composer.json, Dockerfile, docker-compose.yml, artisan, CI | Laravel + Vue 3 (package.json-confirmed) | **In scope** |
| Trello-Board-Init | 2026-03-20 | requirements.txt | Python CLI tool | **In scope** |
| Triton | 2026-08-13 | pyproject.toml, docker-compose.yml, CI | Python + FastAPI (pyproject-confirmed) | **In scope** |
| laravel-task-manager | 2026-03-04 | package.json, composer.json, artisan | Laravel + Vite frontend | Excluded |
| laravel-task-manager-api | 2026-03-04 | package.json, composer.json, artisan | Laravel API | Excluded |
| MarvinLeRouge.dev Homepage | 2026-03-28 | none | Static HTML/CSS portfolio site | Excluded |
| MarvinLeRouge-github | 2026-03-13 | none | GitHub profile README repo, not an application | Excluded |
| PlayWithPi | 2026-05-21 | none (no manifest, pure scripts) | Python, has its own CLAUDE.md and `documentation/` | Excluded |
| Portfolio-Engineering-Radar | 2026-08-24 | none yet | This project itself | **In scope (self-audit)** |
| project-templates | 2026-05-07 | none | Scaffolding templates, not a shipped product | Excluded |
| Recherche emploi | 2026-06-19 | none | Personal job-search material: CVs, PDFs, personal notes | Excluded |
| Summit-Stats-clean | 2026-03-16 | package.json, composer.json, artisan, CI | Same remote as Summit-Stats.git, older last commit — stale local clone | Excluded |
| temp | 2026-03-12 | none | Same remote as Summit-Stats.git, named `temp` — stale local clone | Excluded |
| Training | 2026-06-11 | none | Appears to hold coding exercises (e.g. `backtracking/`) | Excluded |

**DECIDED — confirmed portfolio scope (D1):** the audited portfolio is exactly these 10 repositories: **CC-Beacon, GeoChallenge-Tracker, HexaRot, HiveMind, JobFlow, Stamped, Summit-Stats, Trello-Board-Init, Triton, and Portfolio-Engineering-Radar itself (self-audit, included from the start).** All other repositories listed above are out of scope. This also resolves D2 (duplicates excluded), D3 (`Recherche emploi` excluded), and D4 (CC-Beacon confirmed in scope) — see `docs/open-decisions.md`.

---

## 3. Constraints analysis (INTERPRETATION)

- **Monorepos exist in the portfolio.** HexaRot and HiveMind each hold multiple sub-packages (backend/frontend) under one repository and one `package.json` workspace root. The audit unit therefore cannot always be "one manifest file = one stack"; the tool orchestrator must be able to discover and analyze multiple sub-projects inside a single repository.
- **Mixed stacks per repository are the norm, not the exception** (Laravel API + Vite frontend, FastAPI + Vue frontend). Criteria and tooling must be composable per detected sub-stack rather than one tool set per repo.
- **No tool is pre-installed globally.** The audit system must ship and pin its own toolchain rather than rely on whatever a given repository's `devDependencies` happen to include — otherwise tool versions (and therefore scores) would drift per repo and break comparability (violates the stability principle in prompt §3).
- **Activity recency varies widely** (2026-03 to 2026-08): older/abandoned repos should still be audited, but low activity is itself a possible finding, not a reason to skip a repo. **Confirmed (2026-08-25):** the developer explicitly wants tracking on inactive projects too, so they can be picked back up and improved via the roadmap (§10) — inactivity is not a reason to deprioritize a repo's findings out of the living roadmap.
- **One repository already has a `docker-compose.prod.yml` pointing at a VPS (CC-Beacon).** This is an external dependency that must not be contacted during a local audit.
- **Sensitive personal data exists on disk** (`Recherche emploi`: CVs, PDFs with personal information) — confirmed excluded from scope. Still confirms prompt §27's requirement that the audit engine must never copy file contents wholesale into the audit database, since some in-scope repos (e.g. `.env`-style local config) may hold their own secrets.

---

## 4. Proposed global architecture

```text
Repositories (local, read-only)
        ↓
Repo discoverer (identifies sub-projects per repo: backend/, frontend/, api/, ...)
        ↓
Analysis runner (invokes pinned tools per detected sub-stack)
        ↓
Raw tool results (JSON, kept as-is, one file per tool run)
        ↓
Normalizer (raw results → Finding / Score, evidence-based, tagged with confidence)
        ↓
SQLite database (structured, versioned methodology attached to each audit)
        ↓
Report generator (global/ and repositories/<name>/ Markdown)
        ↓
Dashboard (FastAPI read/write API + Vue 3 SPA)
```

Proposed components, to live in this repository:

- **`radar-audit`** (Python) — orchestrates repo discovery, tool execution, and normalization. Runs one repo (or the whole portfolio) at a time, entirely offline except where a criterion explicitly requires network access (flagged, opt-in — see `docs/open-decisions.md#d6`).
- **`radar-api`** (FastAPI) — serves audit data to the dashboard; read endpoints for portfolio/repo/comparison/cross-cutting views; narrow write endpoints limited to roadmap task status changes (human-confirmed only, never auto-set to `DONE`).
- **`radar-dashboard`** (Vue 3 + Vite) — SPA consuming `radar-api`, implementing the four views from prompt §13 plus the Next Best Actions panel (§14).
- **`radar.db`** (SQLite file) — local, gitignored, holds all structured audit data and raw tool results.
- **Reports** (`global/*.md`, `repositories/<name>/*.md`) — generated *from* the database, never hand-edited, never the source of truth.

Launch target: `docker compose up` (prompt §25), wiring `radar-api` + `radar-dashboard` + a mounted SQLite volume. `radar-audit` runs as a separate CLI invocation (scheduled manually or via cron later), not as a long-running service.

---

## 5. Proposed data model

| Entity | Purpose | Key relations |
|---|---|---|
| `Repository` | One audited local repo (or sub-project within a monorepo) | 1—N `Audit` |
| `MethodologyVersion` | Frozen snapshot of taxonomy/criteria/weights/scoring rules | 1—N `Audit` |
| `Category` | Top-level taxonomy branch (e.g. Security) | 1—N `Criterion`, belongs to `MethodologyVersion` |
| `Criterion` | Measurable unit within a category | 1—N `Finding`, 1—N `Score` |
| `Audit` | One run of the methodology against one repository at one point in time | 1—N `Score`, 1—N `Finding`, 1—N `ToolResult`, references one `MethodologyVersion` |
| `ToolResult` | Raw, unmodified output of one tool invocation | belongs to `Audit`, source for `Finding` |
| `Finding` | Evidence-based observation (id, repository, category, criterion, severity, description, evidence, file, line, tool, recommendation, estimated_effort, confidence, detected_at, status, `human_verdict`) | belongs to `Audit` and `Criterion`, 0—N `Evidence`, may generate `ImprovementTask` |
| `Evidence` | Minimal proof backing a `Finding` or a `Score` (no wholesale file copies, per §27) | belongs to `Finding` or `Score` |
| `Score` | Numeric result at criterion/category/global level, with confidence | belongs to `Audit` and `Criterion`/`Category` |
| `Recommendation` | Actionable suggestion distinct from the observation itself | belongs to `Finding` |
| `ImprovementTask` | Roadmap-ready unit of work | N—N `Finding` (a task can resolve several findings; a finding can spawn one task) |
| `RoadmapItem` | Task + status + priority + effort/impact/dependencies/timestamps, per prompt §16 | wraps `ImprovementTask`, references `Evidence` required to reach `DONE` |
| `Snapshot` | Immutable portfolio/repo state at audit time, for trend comparison | references `Audit` + `MethodologyVersion` |

Raw `ToolResult` payloads are retained (subject to §27 minimization) specifically to support the "re-score historical audits" mechanism from prompt §21.

**`human_verdict` field (decided 2026-08-26, see `docs/open-decisions.md#d14`):** `Finding` carries an optional verdict (`UNREVIEWED` / `TRUE_POSITIVE` / `FALSE_POSITIVE`), set from the dashboard via the same `human_confirmation`-type `Evidence` mechanism already used for criterion `DONE` transitions (§8), applied here at the individual-finding level. This is what makes §8's "known false-positive pattern for that tool" concrete: verdicts are aggregated per (tool, rule) pair across the audit history, and a rule with a significant rejection rate has its baseline `Finding` confidence downgraded for future audits, until the rule is fixed or retired.

---

## 6. Proposed initial taxonomy

The 15 categories from prompt §4 are retained as-is for the Phase 0 proposal. No merge/removal is justified yet without pilot data — finalizing (and justifying any change) is explicitly Phase 2's job, informed by Phase 3 calibration.

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

Three candidates worth flagging for Phase 2 review given the target profile (solo fullstack developer, not an enterprise team): categories 9 (Observability) and 13 (Data quality) may need scope-narrowing (e.g. "structured logging present" rather than "full observability stack") so they don't penalize small personal projects for lacking enterprise-grade operations. Category 10 (API/UX/product quality) is flagged separately (2026-08-26): "product quality" is comparatively hard to quantify objectively versus tool-backed categories like Security or Testing, and its measurable sub-criteria need clearer definition in Phase 2. None of this taxonomy has been tested against the actual structure of the in-scope repositories yet — that validation is explicitly Phase 3's job (pilot calibration), not Phase 0.

**First concrete criterion, decided during Phase 0 review (2026-08-25) — see `docs/open-decisions.md#d11`:**

| Field | Value |
|---|---|
| Category | 7. DevOps / CI-CD |
| Criterion | Reverse proxy / local-prod environment parity (Traefik) |
| Rationale | Deliberate, portfolio-wide standardization choice by the developer (prompt §24 "standardisation souhaitable"), not an externally-imposed stack preference |
| Status model | `DONE` / `IN_PROGRESS` / `TODO` / `N/A` — tracks rollout progress without penalizing repos where the criterion doesn't apply |
| Evidence | Presence of Traefik labels or a dedicated routing file **inside the repository**, checked separately for local and prod compose files |
| Status → score mapping | `DONE`=10, `IN_PROGRESS`=5, `TODO`=0, `N/A`=excluded from category average (weight redistributed, per §7's N/A rule) |
| `DONE` conditions | Both local and prod environments covered and consistent |
| `IN_PROGRESS` conditions | Only one environment covered, or configuration incomplete |
| `TODO` conditions | Repo exposes a long-lived web service (FastAPI/Laravel/Node) with no Traefik config at all |
| `N/A` conditions | Repo has no long-lived web-facing service (e.g. a CLI tool) |
| False positives | Labels present but never exercised (no runtime verification) — mitigated by the human-confirmation gate in §8 |

**Second concrete criterion, decided during Phase 0 review (2026-08-25) — see `docs/open-decisions.md#d12`:**

| Field | Value |
|---|---|
| Category | 2. Code quality |
| Criterion | Pre-commit quality gate (lint / format / type-check hooks) |
| Rationale | Deliberate, portfolio-wide standardization choice by the developer: block defective code from entering history rather than catching it later in CI. The enforcement mechanism is Git-hook/CI-flavored, but the measured object is code-quality baseline, hence Code quality rather than DevOps/CI-CD |
| Evidence | Presence of a recognized pre-commit tool config (`.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`, or an equivalent versioned Git hook) **inside the repository** |
| Coverage matrix | Expected cells = applicable (validator type × domain) pairs, where validator type ∈ {lint, format, type-check} and domain ∈ {backend, frontend} (only domains actually present in the repo count) |
| Status model | `DONE` / `IN_PROGRESS` / `TODO` / `N/A` — same 4-state model as the Traefik criterion (§6 above), for dashboard consistency |
| Status → score mapping | `DONE`=10 (matrix 100% covered); `TODO`=0 (no pre-commit hook config detected at all); `N/A`=excluded from category average, weight redistributed (repo has no domain where any validator type is meaningful); `IN_PROGRESS`=**computed**, not fixed — `score = (covered cells / applicable cells) × 10` |
| `IN_PROGRESS` detail | Each uncovered cell (e.g. "no type-check hook on frontend") generates its own `Finding`, so the gap is visible without a full manual audit |
| False positives | Hook config present but not actually enforced (e.g. `--no-verify` culture, hook installed but not run in CI as a backstop) — mitigated by the human-confirmation gate in §8 when status computes to `DONE` |

**Third concrete criterion, decided during Phase 0 review (2026-08-26) — see `docs/open-decisions.md#d13`:**

| Field | Value |
|---|---|
| Category | 10. API / UX / product quality (provisional — flagged for a Phase 2 split candidate, see below) |
| Criterion | Graphic/visual design quality |
| Rationale | No industry-recognized objective scale exists for pure aesthetics (unlike accessibility/WCAG or performance/Lighthouse) — this criterion accepts that limitation explicitly rather than pretending a fully deterministic measure exists |
| Scoring model | Standard 0-10 anchored scale (§7), **not** the 4-state adoption model used by Traefik/pre-commit — this criterion scores existing quality, it doesn't track rollout of a practice |
| Evidence — factual layer | `impeccable audit` findings (WCAG contrast, responsive behavior) — deterministic, tool-based, confidence HIGH |
| Evidence — interpretive layer | `impeccable critique`, restricted to heuristic #8 (Aesthetic and Minimalist Design) and Assessment A's visual observations (typography, color, hierarchy, composition) — **not** the full Nielsen 10-heuristic score, which bundles unrelated functional/UX heuristics out of scope for this criterion. LLM-subagent-based judgment, confidence MEDIUM/LOW |
| Confidence aggregation | Per §8's minimum rule, the criterion's overall confidence is dragged down to the interpretive layer's MEDIUM/LOW by the factual layer's HIGH — this is intended, not a defect, since the interpretive layer is what actually captures "aesthetics" |
| `N/A` conditions | Repo has no UI at all (CLI/script tools, e.g. `JobFlow`, `Trello-Board-Init`) — excluded from category average, weight redistributed |
| Human-confirmation gate | Applies per §8 whenever this criterion's score computes into the maximal band from a lower prior value, given confidence is never HIGH end-to-end |
| False positives | LLM critique judgment can vary run-to-run (subjective by nature) — mitigated by only trusting the narrow heuristic-#8-plus-visual-observations slice, not the full critique score, and by the confirmation gate |

**Taxonomy note (Phase 2 candidate, flagged 2026-08-26):** categories 9 (Observability), 10 (API/UX/product quality), and 13 (Data quality) are all flagged for review once pilot data exists. For category 10 specifically, a concrete split candidate has emerged: "API design quality" (arguably closer to category 1, Architecture & design) vs. a narrower "UX/Visual/Product quality" — bundling API contract quality with visual design dilutes both. No decision now; Phase 3 pilot findings will inform whether the split is worth the added taxonomy complexity.

---

## 7. Proposed scoring system

- **Scale:** 0–10 per criterion, anchored at fixed levels (0/2/4/6/8/10) each tied to an explicit, evidence-based condition — never a free-form 0–10 impression.
- **Aggregation:** weighted average of criteria → category score; weighted average of categories → global score. Weights are defined per criterion/category in the `MethodologyVersion` data, not hardcoded.
- **Critical penalties:** a defined set of criteria can act as a hard cap on their category regardless of the weighted average (e.g. a committed secret caps Security low even if other security criteria score well) — the list of capping conditions is part of the versioned methodology, not implicit code.
- **N/A handling:** a criterion marked not-applicable is excluded from its category's weighted average and its weight is redistributed among the remaining applicable criteria of that category; the exclusion reason is recorded.
- **Missing data handling:** a criterion that could not be evaluated (tool failed, no evidence available) is scored as absent rather than defaulted to a neutral value, and its category confidence is downgraded accordingly — it is never silently treated as 0 or as N/A.
- Every score record carries its own `confidence` field; scores are never presented as bare numbers without it.

---

## 8. Proposed confidence system

- **Levels:** HIGH / MEDIUM / LOW, attached to every `Finding` and every `Score`.
- **Finding confidence** depends on: whether the underlying evidence came from a deterministic tool (baseline HIGH) vs. an AI interpretation of ambiguous output (baseline MEDIUM/LOW), rule maturity (a well-established rule vs. a custom/experimental one), and whether the finding matches a known false-positive pattern for that tool.
- **Aggregation rule:** category/global confidence is the **minimum** (worst-case) of its constituent confidences, not an average — so a handful of low-confidence inputs cannot be diluted into an apparently solid aggregate score.
- Confidence is stored as data, not computed only at render time, so historical audits keep their original confidence even if aggregation rules evolve.
- **Human confirmation gate for maximal-state transitions (decided 2026-08-25, see `docs/open-decisions.md#d11`):** when a criterion's status/score moves **up to its maximal state** (e.g. `DONE`) from a lower state at a given audit, and the supporting evidence is not `HIGH` confidence, the new value is **not** committed automatically. It is held as `PENDING_CONFIRMATION` and surfaced in the dashboard for an explicit human decision ("criterion X is moving to DONE — do you confirm the capability is actually in place?"). Confirming records the human decision itself as an `Evidence` of type `human_confirmation` attached to the `Score`; rejecting keeps the criterion at its real state and generates a `Finding` documenting the static-evidence-vs-reality gap (useful anti-false-positive signal for later calibration). This generalizes prompt §17's roadmap rule ("a task is not DONE just because code changed") down to the criterion level, and is not limited to the Traefik criterion in §6 — any criterion using a similar status model inherits this gate.

---

## 9. Proposed methodology versioning strategy

- Format: `Quality Framework vMAJOR.MINOR`.
- **MINOR bump:** clarified criterion wording, adjusted evidence threshold, equivalent tool swap (same evidence, different tool), additive non-breaking criteria.
- **MAJOR bump:** category added/removed/merged, weight redistribution beyond a defined tolerance, change to the scoring scale itself.
- The taxonomy/criteria/weights are stored as versioned data (e.g. one file per `MethodologyVersion`, kept in the database and/or versioned in-repo), not embedded in code logic.
- Every `Audit` stores the exact `MethodologyVersion` id used.
- **Comparability rule:** audits sharing the same MAJOR version are directly comparable on a trend line; audits across a MAJOR boundary are shown as a labeled discontinuity, never silently merged.
- **Re-scoring:** because raw `ToolResult` data is retained, a batch job can re-run normalization against a newer `MethodologyVersion` to produce a comparable historical re-score — explicitly presented as a re-score, never overwriting the original audit record.

---

## 10. Proposed roadmap strategy

- `RoadmapItem` wraps one or more `ImprovementTask`, each linked to the `Finding`(s) that justified it (N—N), so a single task like "standardize error handling" can be traced back to findings across several repositories.
- Status machine: `BACKLOG → PLANNED → IN_PROGRESS → BLOCKED → DONE | WONT_FIX`.
- **DONE requires attached Evidence** (prompt §17): a passing test added, a tool no longer flagging the issue, a re-audit result — a code diff alone is never sufficient.
- A divergence check (prompt §18) compares roadmap status against the latest audit's findings for the same criteria:
  - roadmap says `DONE` but the finding reappears → **regression** flag.
  - the relevant code area changed materially but the roadmap entry is untouched past a defined staleness threshold → **stale roadmap** flag.

---

## 11. Proposed dashboard architecture

- **Backend (`radar-api`, FastAPI):** read endpoints for the four views (Portfolio, Repository, Comparison, Cross-cutting — *problems common to several repositories, e.g. "Error handling inconsistent → 4 repos → high global impact → 6h estimated effort"; this is prompt §13's priority view*) plus Next Best Actions; narrow write endpoints strictly for roadmap status transitions, always human-triggered.
- **Frontend (`radar-dashboard`, Vue 3 + Vite):** SPA consuming `radar-api`; a lightweight charting library (candidate, to confirm in Phase 1) for trend lines and category breakdowns.
- **Storage:** single SQLite file, gitignored, local only.
- **Launch (decided 2026-08-26, see `docs/open-decisions.md#d5`):** `docker compose up`, confirmed. Full containerization — including `radar-audit`, not just `radar-api`/`radar-dashboard` — chosen deliberately for environment control, even though this tool has no deployment target of its own.

---

## 12. Candidate toolchain (to validate in Phase 1)

Install strategy: given no tool is globally installed (§1), the audit system pins its own tool versions (via `uv`/`uvx`, `pnpm dlx`/`npx`, or per-repo isolated Composer/PHP installs) rather than depending on each target repo's own `devDependencies` — this keeps tool versions (and therefore score stability) under the audit system's control, independent of what each repo happens to have configured.

| Domain | Candidates |
|---|---|
| Security | Semgrep, Gitleaks, Trivy (filesystem scan), `pip-audit`, `npm`/`pnpm audit`, `composer audit` |
| Python | Ruff, mypy, pytest + coverage, a complexity tool (candidate, e.g. `radon`) |
| JavaScript / TypeScript | ESLint (respecting each repo's own config as *input*, not audit config), `tsc --noEmit`, Vitest/Playwright (where present), a dead-dependency tool (candidate, e.g. `knip`/`depcheck`) |
| PHP | PHPStan, Pint or PHP_CodeSniffer, PHPUnit |
| Architecture / dependencies | JS: `madge` (cycles); Python: `import-linter`/`pydeps`; PHP: `deptrac` — all candidates, none validated yet |
| Containers | Hadolint (Dockerfile lint), Trivy (image scan) |
| Git / CI | `actionlint` (GitHub Actions lint); branch-protection/commit-quality checks need the GitHub API — flagged as an external dependency, see `docs/open-decisions.md#d6` |
| Pre-commit hooks (added 2026-08-26) | `pre-commit` (Python-ecosystem framework), `husky`, `lefthook` — investigate config content, not just presence, to support the coverage-matrix evidence needed by the pre-commit quality gate criterion (`docs/system-design.md#6`, D12) |

None of these are installed or run yet. Phase 1's job is to actually try each candidate against the pilot repository and keep only what proves reliable and low-noise.

---

## 13. Points requiring a human decision

See `docs/open-decisions.md` for the full list (D1–D14).
