# 0005. Taxonomy adjustments before calibration

**Status:** Proposed / deferred
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

The 15 categories proposed for Quality Framework v1.0 were adopted as-is,
with categories 9 (Observability) and 13 (Data quality) flagged as
possibly needing a narrower, profile-appropriate scope for a portfolio of
mostly small, single-developer projects.

## Decision

No decision is made at this point. The default is to keep all 15
categories and let Phase 3 pilot calibration surface concrete evidence
for any merge or split, rather than adjusting the taxonomy speculatively
before any real audit data exists. This ADR exists to record that the
question was raised and deliberately deferred, not silently dropped.

## Consequences

- Categories 9 and 13 ship in Quality Framework v1.0 at their originally
  proposed scope; any narrowing is deferred to evidence gathered during
  pilot audits.
- This decision has no immediate implementation impact; it is a
  placeholder for a future revisit.

## Alternatives considered

- **Narrow categories 9 and 13 immediately:** rejected as premature
  without pilot data to justify the specific narrowing.
- **Drop the flag entirely:** rejected, since the concern is real enough
  to want it tracked rather than forgotten before Phase 2.
