# 0009. Pre-commit quality gate criterion

**Status:** Accepted
**Date:** 2026-08-25
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

Raised during the point-by-point review of the Phase 0 constraints
analysis ("no tool pre-installed globally" point). The developer wants to
generalize pre-commit hooks (lint/format/type-check) across the whole
portfolio, to block defective code before it enters history rather than
catching it later in CI.

## Decision

New taxonomy criterion, category 2 (Code quality): "Pre-commit quality
gate (lint / format / type-check hooks)". Reuses the 4-state status model
introduced for the Traefik criterion (`DONE`/`IN_PROGRESS`/`TODO`/`N/A`),
but with a coverage-matrix approach: expected cells are the applicable
(validator type x domain) pairs (lint/format/type-check x
backend/frontend, only domains actually present in the repo). The
`IN_PROGRESS` score is computed as `covered / applicable x 10` rather
than a fixed midpoint, and each uncovered cell generates its own
`Finding`. Subject to the same human-confirmation gate as any criterion
computing to `DONE`.

## Consequences

- The scoring model for status-based criteria now needs to support a
  computed `IN_PROGRESS` score derived from a coverage matrix, not just a
  fixed value.
- Each missing pre-commit hook cell is individually actionable as its own
  `Finding`, rather than the criterion collapsing to a single pass/fail
  signal.
- This is the same criterion this project's own `.pre-commit-config.yaml`
  is meant to satisfy, i.e. the audit system dogfoods the criterion it
  defines.

## Alternatives considered

- **Binary DONE/TODO status only:** rejected, doesn't reward partial
  coverage (e.g. lint hook present but no type-check hook) with any
  visible progress signal.
- **Fixed midpoint score for IN_PROGRESS:** rejected in favor of the
  coverage-ratio computation, which reflects actual partial adoption
  rather than an arbitrary constant.
