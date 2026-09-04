# 0006. Pilot repository selection

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #5 (`chore/phase-3-pilot-selection`), commit 2a00b0b

## Context

Phase 3 calibration needs a pilot repository representative of the
portfolio's main stacks. Three candidates were confirmed as
representative during the Phase 0 review:

- **GeoChallenge-Tracker**: the most complete/mature repo (FastAPI +
  MongoDB + Vue 3, has DESIGN.md, CONTRIBUTING, CI, codecov), the best
  stress-test for the full taxonomy.
- **Summit-Stats**: Laravel + Vue 3 + Docker, covers the PHP side.
- **JobFlow**: a small, focused Python CLI, useful to check the framework
  doesn't over-penalize a deliberately minimal tool.

## Decision

**GeoChallenge-Tracker** is the Phase 3 pilot, chosen for exercising the
widest slice of the taxonomy in a single pass. Summit-Stats and JobFlow
stay as reserve candidates for a targeted cross-check if the
GeoChallenge-Tracker run leaves parts of the framework (PHP-specific
tooling, or the deliberately-minimal-tool case) under-exercised.

## Consequences

- The first full manual audit pass and the resulting framework
  corrections are calibrated primarily against a FastAPI + MongoDB +
  Vue 3 codebase.
- Summit-Stats was later run as a second pilot audit specifically to
  check cross-repo consistency on the PHP/Laravel side (see
  [`docs/pilot-audit-summit-stats.md`](../pilot-audit-summit-stats.md)),
  confirming the reserve-candidate plan.

## Alternatives considered

- **Start with Summit-Stats or JobFlow:** rejected, neither exercises as
  much of the taxonomy in a single pass as GeoChallenge-Tracker does.
- **Run all three pilots before any framework correction:** rejected as
  unnecessarily slow; corrections from the first pilot were applied
  before deciding whether a second pilot was needed at all.
