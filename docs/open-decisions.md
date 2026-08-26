# Open Decisions — Phase 0

Each item requires an explicit human decision before Phase 1/2 can proceed on the affected area. Nothing here has been decided unilaterally.

---

## D1 — Portfolio scope: which repositories are audited — **DECIDED (2026-08-25)**

20 local repositories were found (see `docs/system-design.md#2`).

**Confirmed portfolio scope (10 repositories):** CC-Beacon, GeoChallenge-Tracker, HexaRot, HiveMind, JobFlow, Stamped, Summit-Stats, Trello-Board-Init, Triton, and **Portfolio-Engineering-Radar itself (self-audit, included from the start, not deferred)**.

**All other repositories are out of scope:** laravel-task-manager, laravel-task-manager-api, MarvinLeRouge.dev Homepage, MarvinLeRouge-github, PlayWithPi, project-templates, Recherche emploi, Summit-Stats-clean, temp, Training.

This decision resolves D2, D3, and D4 below.

---

## D2 — Duplicate/stale repositories — **DECIDED (2026-08-25, via D1)**

`Summit-Stats-clean` and `temp` both point to the same remote as `Summit-Stats` (`github.com/MarvinLeRouge/Summit-Stats.git`) and have older last-commit dates. They look like stale local clones rather than intentional forks.

Resolved by D1: both are outside the confirmed portfolio scope. No further action needed.

---

## D3 — Sensitive repository: "Recherche emploi" — **DECIDED (2026-08-25, via D1)**

Contains personal data: CVs (PDF/Markdown), job-application tracking, personal notes. No engineering content to audit.

Resolved by D1: excluded from the confirmed portfolio scope, consistent with the source-minimization principle in prompt §27.

---

## D4 — CC-Beacon's status in the portfolio — **DECIDED (2026-08-25, via D1)**

CC-Beacon is the developer's own session-tracking tool (FastAPI + web), already referenced by the assistant's global tooling, and ships a `docker-compose.prod.yml` targeting an external VPS.

Resolved by D1: **CC-Beacon is in scope.** Constraint carried forward: the audit must never contact the VPS referenced in `docker-compose.prod.yml`; local-only static/deterministic checks only.

---

## D5 — Dashboard stack and launch mechanism — **DECIDED (2026-08-26)**

Prompt §25 suggests Vue 3 + FastAPI + SQLite, optionally behind `docker compose up`.

**Decided:** full containerization, `docker compose up`, including `radar-audit` alongside `radar-api`/`radar-dashboard` — not just the two-service subset. Chosen deliberately for environment control, even though the tool has no deployment target of its own and runs on a single machine for a single user. See `docs/system-design.md#11`.

---

## D6 — External network access for certain criteria — **DECIDED (2026-08-26)**

Some potentially valuable criteria require the GitHub API (branch protection rules, PR review requirements, Actions run history beyond what's in the local `.git`) — this conflicts with the local-first principle (prompt §26) unless explicitly opted into.

**Decided:** allow GitHub API access, **read-only** (repos, commits, PRs — no write scope, ever), explicit opt-in per run (e.g. `--allow-github-api`), not enabled by default. The data model clearly tags remote-fetched evidence as distinct from local static evidence (`.git`), consistent with the local-first principle (prompt §26).

---

## D7 — Toolchain installation strategy — **DECIDED (2026-08-26)**

No analysis tool (Semgrep, Ruff, ESLint, PHPStan, Trivy, etc.) is installed globally on this machine (see `docs/system-design.md#1`).

**Decided:** the audit system pins and runs its own tool versions ephemerally (`uvx`, `pnpm dlx`/`npx`, isolated Composer installs, or containers), independent of what each target repo declares in its own `devDependencies`. "Ephemeral" means not persistently installed in the global system environment (not in PATH, isolated per pinned version) — not "re-downloaded on every run": first invocation of a given pinned version downloads and caches it locally (e.g. `~/.cache/uv`, npx cache), subsequent invocations reuse the cache.

This directly affects score stability (prompt §3): if tool versions aren't pinned by the audit system itself, upgrading a repo's own linter could silently shift its score between audits.

---

## D8 — Taxonomy adjustments before calibration

The 15 categories from prompt §4 are proposed as-is for v1.0 (see `docs/system-design.md#6`), with categories 9 (Observability) and 13 (Data quality) flagged as possibly needing narrower, profile-appropriate scope.

**Decision needed:** none right now — default is to keep all 15 and let Phase 3 (pilot calibration) surface concrete evidence for any merge/split. Flagging here only so the choice isn't lost before Phase 2.

---

## D9 — Pilot repository selection (Phase 3 pre-requisite) — **candidates confirmed representative (2026-08-26), final pick deferred**

Candidates representative of the portfolio's main stacks, confirmed as such during the Phase 0 review:

- **GeoChallenge-Tracker** — most complete/mature repo (FastAPI + MongoDB + Vue 3, has DESIGN.md, CONTRIBUTING, CI, codecov) — best stress-test for the full taxonomy.
- **Summit-Stats** — Laravel + Vue 3 + Docker, covers the PHP side.
- **JobFlow** — small, focused Python CLI, useful to check the framework doesn't over-penalize a deliberately minimal tool.

**Decision needed:** final pilot pick still deferred to the start of Phase 3 (not blocking Phase 0/1) — the candidate list itself is no longer open.

---

## D10 — Documentation / report / UI language — **DECIDED (2026-08-26)**

The master prompt is in French; this repository's own README is bilingual (English primary, `README.fr.md` translation); generated docs so far (`system-design.md`, this file) were written in English for consistency with the versioned codebase language convention.

**Decided:** English for generated reports, findings, and dashboard UI text. French kept for direct conversation, and possibly a `.fr` mirror of top-level docs only, matching the README pattern.

---

## D11 — Traefik reverse-proxy criterion and human-confirmation gate — **DECIDED (2026-08-25)**

Raised during the point-by-point review of `docs/system-design.md`§1. The developer standardizes on Docker + Traefik, both locally and remotely, across the portfolio for local/prod parity ("reliable production behavior = professional behavior").

**Decided:**
1. **New taxonomy criterion**, category 7 (DevOps/CI-CD): "Reverse proxy / local-prod environment parity (Traefik)" — full definition in `docs/system-design.md#6`. Tracked with a 4-state status model (`DONE`/`IN_PROGRESS`/`TODO`/`N/A`) rather than a free-form 0-10 score, mapped onto the generic scoring rules (status→score mapping, N/A excluded with weight redistribution).
2. **General human-confirmation gate**, added as a system-wide rule in `docs/system-design.md#8`: whenever any criterion's status/score moves up to its maximal state (e.g. `DONE`) from a lower prior state, and the supporting evidence is not `HIGH` confidence, the transition is held as `PENDING_CONFIRMATION` and requires explicit human confirmation in the dashboard before being committed. Confirmation is recorded as a `human_confirmation`-type `Evidence`; rejection generates a `Finding` documenting the static-evidence-vs-reality gap. This generalizes prompt §17's roadmap-DONE rule down to the criterion level and applies to any criterion using a similar status model, not just Traefik.

Canonical Traefik configuration is expected to live inside each repository (compose labels or a dedicated file); the external `~/projets/traefik/` folder is a manual convenience grouping, excluded from audit scope (see `docs/system-design.md#1`).

---

## D12 — Pre-commit quality gate criterion — **DECIDED (2026-08-25)**

Raised during the point-by-point review of `docs/system-design.md`§3 (constraints analysis, "no tool pre-installed globally" point). The developer wants to generalize pre-commit hooks (lint/format/type-check) across the whole portfolio, to block defective code before it enters history rather than catching it later in CI.

**Decided:** new taxonomy criterion, category 2 (Code quality): "Pre-commit quality gate (lint / format / type-check hooks)" — full definition in `docs/system-design.md#6`. Reuses the 4-state status model from the Traefik criterion (`DONE`/`IN_PROGRESS`/`TODO`/`N/A`), but with a coverage-matrix approach: expected cells = applicable (validator type × domain) pairs (lint/format/type-check × backend/frontend, only domains actually present in the repo). `IN_PROGRESS` score is computed as `covered / applicable × 10` rather than a fixed midpoint, and each uncovered cell generates its own `Finding`. Subject to the same human-confirmation gate (`docs/system-design.md#8`) when status computes to `DONE`.

---

## D13 — Graphic design quality criterion — **DECIDED (2026-08-26)**

Raised at the end of the prior session, discussed at the start of this one, before Section 7 of `docs/system-design.md`.

**Decided:** new taxonomy criterion, category 10 (API/UX/product quality, provisional) — "Graphic/visual design quality", full definition in `docs/system-design.md#6`. Standard 0-10 scoring (not the 4-state adoption model), combining a deterministic factual layer (`impeccable audit`: WCAG contrast, responsive — HIGH confidence) with a narrow interpretive layer (`impeccable critique`, restricted to heuristic #8 "Aesthetic and Minimalist Design" plus Assessment A's visual observations only — not the full Nielsen score — MEDIUM/LOW confidence). Repos with no UI (`JobFlow`, `Trello-Board-Init`) are `N/A`. Subject to the human-confirmation gate (`docs/system-design.md#8`) given confidence is never HIGH end-to-end.

Also decided: category 10 is flagged as a Phase 2 split candidate ("API design quality" vs. narrower "UX/Visual/Product quality") — not resolved now, deferred to Phase 3 pilot data per the existing D8 default.

---

## D14 — `human_verdict` on Finding: false-positive feedback loop — **DECIDED (2026-08-26)**

Raised during the point-by-point review of `docs/system-design.md`§8 (confidence system): the "known false-positive pattern" language had no concrete data-model support.

**Decided:** `Finding` gains an optional `human_verdict` field (`UNREVIEWED`/`TRUE_POSITIVE`/`FALSE_POSITIVE`), set via the dashboard using the same `human_confirmation`-type `Evidence` mechanism as the criterion-level confirmation gate (D11), but applied per individual finding. Verdicts are aggregated per (tool, rule) pair across audit history; a rule with a significant rejection rate has its baseline `Finding` confidence downgraded for future audits. Full definition in `docs/system-design.md#5` and `#8`.

---

## D15 — External network access for dependency freshness checks — **DECIDED (2026-08-26)**

Raised during Phase 1 toolchain evaluation of the Security domain: `pip-audit`/`pnpm audit`/`composer audit` only detect known CVEs on pinned versions, not staleness (a dependency several majors behind, or abandoned, with no CVE filed). Checking freshness (`pip list --outdated`, `npm outdated`/`pnpm outdated`, `composer outdated`) requires querying the relevant package registry (PyPI, npm, Packagist) for the latest available version — a network dependency distinct from the GitHub API covered by D6.

**Decided:** allow read-only access to public package registries (PyPI, npm, Packagist) to check dependency freshness, opt-in per run (same mechanism as D6, e.g. `--allow-registry-lookup`), not enabled by default. No authentication, no write scope. Feeds category 11 (Dependency management), whose detailed criteria are still deferred to Phase 2 per D8.
