# 0011. human_verdict on Finding: false-positive feedback loop

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

Raised during the point-by-point review of the Phase 0 confidence
system: the design mentioned a "known false-positive pattern" concept
with no concrete data-model support to actually record and learn from
human feedback on findings.

## Decision

`Finding` gains an optional `human_verdict` field
(`UNREVIEWED`/`TRUE_POSITIVE`/`FALSE_POSITIVE`), set via the dashboard
using the same `human_confirmation`-type `Evidence` mechanism as the
criterion-level confirmation gate (see
[0008](0008-traefik-criterion-and-confirmation-gate.md)), but applied per
individual finding. Verdicts are aggregated per (tool, rule) pair across
audit history; a rule with a significant rejection rate has its baseline
`Finding` confidence downgraded for future audits.

## Consequences

- The system can track, per tool/rule pair, an empirical false-positive
  rate derived from real human feedback rather than a static
  hand-assigned confidence.
- Every `Finding` review decision produces its own evidence trail, the
  same auditable pattern used for criterion-level confirmations.
- Future audits automatically benefit from past corrections: a
  chronically noisy (tool, rule) pair gets downgraded confidence without
  manual intervention.

## Alternatives considered

- **No feedback loop, static confidence per tool/rule:** rejected, this
  was the original gap that made the "known false-positive pattern"
  language meaningless without data-model support.
- **Track verdicts without aggregating them into confidence
  adjustments:** rejected, would collect feedback without ever acting on
  it, defeating the purpose of the feedback loop.
