# Development Roadmap

Tracks progress phase by phase, per the master prompt (`docs/ai/Prompt maître — Portfolio Engineering Quality System.md`).
Checkboxes are updated at the end of each phase. This file will later feed the README roadmap section.

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
- [x] Produce `docs/open-decisions.md`
- [x] **Human review of `docs/open-decisions.md` (D1–D14) — blocks Phase 1**

## Phase 1 — Toolchain discovery and selection

- [x] Evaluate candidate tools per language/domain (security, Python, JS/TS, PHP, architecture/dependencies, containers, Git/CI)
- [x] Validate local availability and licensing of retained tools
- [x] Document the final toolchain and rejected alternatives

## Phase 2 — Final definition of categories, rules, criteria, scoring

- [x] Finalize the taxonomy (categories + justified adjustments)
- [x] Define measurable criteria per category (objective, evidence, tools, levels, weight, dependencies, confidence, false positives)
- [x] Define the hierarchical scoring model (criterion → category → global)
- [x] Define critical penalties, N/A handling, missing-data handling
- [x] Freeze **Quality Framework v1.0**

## Phase 3 — Calibration on a pilot repository

- [x] Select the pilot repository (GeoChallenge-Tracker, see `docs/open-decisions.md#d9`)
- [ ] Run a full audit against it
- [ ] Review criteria relevance, false positives/negatives, weights, effort
- [ ] Correct the framework based on findings
- [ ] Confirm Quality Framework v1.0 as the reference for the first global audit

## Phase 4 — System implementation

- [ ] Implement the data model (Repository, Audit, MethodologyVersion, Category, Criterion, Finding, Score, Evidence, Recommendation, ImprovementTask, RoadmapItem, Snapshot, ToolResult)
- [ ] Implement tool orchestration and raw-result normalization
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
- [ ] Detect roadmap ↔ code divergence
- [ ] Track system self-metrics (score stability, false-positive rate, reproducibility)
