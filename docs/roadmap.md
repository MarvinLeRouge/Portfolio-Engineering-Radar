# Roadmap

> [Version française](roadmap.fr.md) | English version

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
    - [ ] Categories 4-15 (Security, Maintainability, Performance, DevOps/CI-CD, Documentation, Observability/operations, API/UX/product quality, Dependency management, Configuration management, Data quality, Developer experience, Technical debt)
- [ ] Implement the local dashboard (backend + frontend)
- [ ] Implement report generation (global + per-repository)

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
