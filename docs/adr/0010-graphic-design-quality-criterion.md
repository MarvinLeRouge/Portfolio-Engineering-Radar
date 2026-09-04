# 0010. Graphic design quality criterion

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

Visual/graphic design quality has real engineering-adjacent signal
(accessibility, consistency, responsive behavior) but is inherently
harder to score objectively than most other criteria, and risks either
being skipped entirely or scored with unjustified confidence.

## Decision

New taxonomy criterion, category 10 (API/UX/product quality,
provisional): "Graphic/visual design quality". Standard 0-10 scoring
(not the 4-state adoption model), combining a deterministic factual layer
(automated audit: WCAG contrast, responsive behavior, `HIGH` confidence)
with a narrow interpretive layer (restricted to a single heuristic,
"Aesthetic and Minimalist Design", plus limited visual observations, not
a full heuristic-evaluation score, `MEDIUM`/`LOW` confidence). Repositories
with no UI (e.g. JobFlow, Trello-Board-Init) are `N/A`. Subject to the
human-confirmation gate given confidence is never `HIGH` end-to-end.

Also decided: category 10 is flagged as a Phase 2 split candidate ("API
design quality" vs. narrower "UX/Visual/Product quality"), not resolved
at this point, deferred to Phase 3 pilot data per the default established
in [0005](0005-taxonomy-adjustments-deferred.md).

## Consequences

- This is the first criterion in the taxonomy to explicitly mix a
  deterministic layer and an interpretive layer with different
  confidence levels within a single score, rather than a single uniform
  confidence per criterion.
- Repos without a UI never get penalized on this criterion; they're
  excluded via `N/A` with weight redistribution.
- The confirmation gate applies here even though this criterion uses the
  standard 0-10 model, not just the 4-state status model, since the gate
  is defined in terms of confidence level, not scoring model.

## Alternatives considered

- **Skip visual/graphic design entirely:** rejected, loses real signal
  about a portfolio repository's polish.
- **Score it with a full Nielsen heuristic evaluation:** rejected as too
  interpretive/subjective to assign meaningfully to an automated,
  reproducible audit; narrowed to one heuristic plus factual checks
  instead.
