[🇫🇷 Version française](roadmap.fr.md) | 🇬🇧 English version

---

# Roadmap

Published, versioned mirror of the project's development roadmap. The
working, non-versioned tracker (updated more frequently during active
development) lives at `docs/work-in-progress/TODO.md`.

Tracks progress phase by phase. Checkboxes are updated as each phase
advances.

## Phase 0 — Audit system architecture

- [x] Inspect the available local environment
- [x] Identify potentially concerned repositories (read-only, no content changes)
- [x] Identify the stacks in use
- [x] Analyze project constraints
- [x] Propose the overall system architecture
- [x] Propose the data structure
- [x] Propose the initial taxonomy
- [x] Propose the scoring system
- [x] Propose the confidence system
- [x] Propose the methodology versioning strategy
- [x] Propose the roadmap strategy
- [x] Propose the dashboard architecture
- [x] Propose the candidate tool list
- [x] Identify points requiring a human decision
- [x] Produce `docs/system-design.md`
- [x] Produce architecture decision records (`docs/adr/`)
- [x] Human review of the open decisions — blocked Phase 1 until resolved

## Phase 1 — Toolchain discovery and selection

- [x] Evaluate candidate tools per language/domain (security, Python, JS/TS, PHP, architecture/dependencies, containers, Git/CI)
- [x] Validate local availability and licensing of retained tools
- [x] Document the final toolchain and rejected alternatives (`docs/toolchain.md`)

## Phase 2 — Final definition of categories, rules, criteria, scoring

- [x] Finalize the taxonomy (categories + justified adjustments)
- [x] Define measurable criteria per category (objective, evidence, tools, levels, weight, dependencies, confidence, false positives)
- [x] Define the hierarchical scoring model (criterion -> category -> global)
- [x] Define critical penalties, N/A handling, missing-data handling
- [x] Freeze **Quality Framework v1.0** (`docs/quality-framework.md`)

## Phase 3 — Calibration on a pilot repository

- [x] Select the pilot repository (see `docs/pilot-audit-geochallenge-tracker.md`)
- [x] Run a full audit against it (manual pass)
- [x] Review criteria relevance, false positives/negatives, weights, effort
- [x] Run a second pilot audit on a structurally different repository (Laravel/PHP + Vue/JS, see `docs/pilot-audit-summit-stats.md`) to check cross-repo consistency
- [x] Correct the framework based on findings
- [x] Confirm Quality Framework v1.0 as the reference for the first global audit

## Phase 4 — System implementation

- [x] Implement the data model (Repository, Audit, MethodologyVersion, Category, Criterion, Finding, Score, Evidence, Recommendation, ImprovementTask, RoadmapItem, Snapshot, ToolResult)
- [ ] Implement tool orchestration and raw-result normalization
  - [x] Core orchestration engine (`radar-audit`): portfolio config, sub-project discovery, worktree exclusion, `ToolRunner` protocol with crash isolation, Quality Framework v1.0 taxonomy seeding, Repository/Audit resolution, Typer CLI
  - [ ] Raw-result normalization per Quality Framework category (one increment per category)
    - [x] Category 1 — Architecture & design: dependency-cruiser + pydeps, DESIGN.md/ARCHITECTURE.md/ADR presence, radon + static LOC module size
    - [x] Category 2 — Code quality: lint pass rate, type-check pass rate, cyclomatic complexity, pre-commit gate, code duplication
    - [x] Category 3 — Testing & reliability: unit test pass rate, integration tests, CI test execution, E2E test presence
    - [x] Category 4 — Security: dependency vulnerabilities (pip-audit/pnpm audit/Composer audit), secrets in git history (Gitleaks), SAST findings (Semgrep), container image vulnerabilities (Trivy), Dockerfile hardening (Hadolint)
    - [x] Category 5 — Maintainability: complexity hotspots (reuses the category 2 complexity runners), dead code / unused exports (Vulture, Knip, PHPMD unusedcode), documentation-in-code (docvet, phpdoc-checker; JS/TS is a permanent N/A, no candidate tool)
    - [ ] Categories 6-15 (Performance, DevOps/CI-CD, Documentation, Observability/operations, API/UX/product quality, Dependency management, Configuration management, Data quality, Developer experience, Technical debt)
- [ ] Reporting and publication pipeline (see `docs/work-in-progress/reporting-pipeline-notes.md` for the detailed breakdown, dependencies, and tooling)
  - [ ] A. Extend the report contract to render Findings, Evidence, and Recommendations (today it only renders Scores); adopt an explicit three-state model per criterion (scored / not applicable with reason / not yet audited), reusing the existing `Score.na_reason` field and `FindingSeverity` vocabulary rather than inventing new statuses
  - [ ] B. Populate `Recommendation` records from findings, so improvement axes are stored data feeding the report, not just report prose
  - [ ] C. Build a minimal `radar-api` (FastAPI): read endpoints over the existing data model, plus narrow human-confirmed-only write endpoints; this is what hosts all report/finding/recommendation data — never written into audited repos
  - [ ] D. Add a quality-assessment badge (shields.io-style endpoint badge) that audited repos can link from their README, pointing at the radar-hosted report page
  - [ ] E. Build the full `radar-dashboard` (Vue 3 + Vite SPA): score gauges as discrete flat-color bands (reusing the `FindingSeverity` 5-tier palette, not a continuous gradient) for a professional, non-gimmicky look; N/A and not-yet-audited criteria rendered grayed out with the reason surfaced

## Phase 5 — Full portfolio audit

- [ ] Run the audit across all identified repositories
- [ ] Generate global documents (`executive-summary`, `portfolio-scorecard`, `cross-project-analysis`, etc.)
- [ ] Generate per-repository documents

## Phase 6 — Backlog and roadmap construction

- [ ] Convert findings into prioritized improvement tasks
- [ ] Compute ROI indicators (impact/effort/risk reduction, clearly marked as estimates)
- [ ] Publish the living roadmap

## Phase 7 — Continuous tracking and re-audits

- [ ] Re-audit after implementation work
- [ ] Detect resolved/new/regressed findings with evidence
- [ ] Detect roadmap <-> code divergence
- [ ] Track system self-metrics (score stability, false-positive rate, reproducibility)
