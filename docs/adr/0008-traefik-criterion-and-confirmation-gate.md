# 0008. Traefik reverse-proxy criterion and human-confirmation gate

**Status:** Accepted
**Date:** 2026-08-25
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

Raised during the point-by-point review of the Phase 0 system design: the
developer standardizes on Docker + Traefik, both locally and remotely,
across the portfolio for local/prod parity ("reliable production
behavior = professional behavior"). No existing criterion captured this,
and no general mechanism existed for gating a criterion's promotion to
its best possible state behind human confirmation when evidence isn't
fully reliable.

## Decision

1. **New taxonomy criterion**, category 7 (DevOps/CI-CD): "Reverse proxy
   / local-prod environment parity (Traefik)". Tracked with a 4-state
   status model (`DONE`/`IN_PROGRESS`/`TODO`/`N/A`) rather than a
   free-form 0-10 score, mapped onto the generic scoring rules
   (status -> score mapping, `N/A` excluded with weight redistribution).
2. **General human-confirmation gate**, added as a system-wide rule:
   whenever any criterion's status/score moves up to its maximal state
   (e.g. `DONE`) from a lower prior state, and the supporting evidence is
   not `HIGH` confidence, the transition is held as
   `PENDING_CONFIRMATION` and requires explicit human confirmation in the
   dashboard before being committed. Confirmation is recorded as a
   `human_confirmation`-type `Evidence`; rejection generates a `Finding`
   documenting the static-evidence-vs-reality gap. This generalizes the
   roadmap-`DONE` confirmation rule down to the criterion level, and
   applies to any criterion using a similar status model, not just
   Traefik.

Canonical Traefik configuration is expected to live inside each
repository (compose labels or a dedicated file); the external
`~/projets/traefik/` folder is a manual convenience grouping, excluded
from audit scope.

## Consequences

- The data model needs a status-based scoring path (not just numeric 0-10
  scores) and a `human_confirmation`-type `Evidence` kind, both of which
  are now general-purpose rather than Traefik-specific.
- Any criterion adopting the 4-state model automatically inherits the
  confirmation-gate behavior, without needing bespoke logic per
  criterion.
- Manual, out-of-repo infrastructure (like the shared `traefik/` folder)
  is explicitly out of scope, keeping the audit boundary at "what's
  inside the repository."

## Alternatives considered

- **Score Traefik adoption on the standard 0-10 scale:** rejected, a
  binary/near-binary adoption criterion is better represented as a
  status than a continuous score.
- **Apply the confirmation gate only to the Traefik criterion:** rejected
  in favor of a general system-wide rule, since the same reliability
  concern (static evidence promoted to `DONE` without strong enough
  confidence) applies to any status-modeled criterion.
