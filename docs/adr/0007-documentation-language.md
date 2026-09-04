# 0007. Documentation / report / UI language

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

The master prompt driving this project's design is written in French,
but this repository's own README follows a bilingual convention (English
primary, `README.fr.md` translation), and the generated design documents
so far were written in English for consistency with the versioned
codebase's language convention.

## Decision

English for generated reports, findings, and dashboard UI text. French is
kept for direct conversation, and a `.fr` mirror of top-level docs only,
matching the README pattern.

## Consequences

- All audit output consumed by the dashboard (findings, reports, UI
  copy) is English-only; no localization layer is needed for generated
  content.
- Versioned reference documentation follows the bilingual
  English-default / `.fr.md`-mirror convention, while generated,
  frequently-changing content (changelog, ADRs, audit reports) stays
  English-only to avoid translating fast-moving or auto-generated text.

## Alternatives considered

- **Bilingual dashboard UI and reports:** rejected as unnecessary
  maintenance overhead for a single-user, French-speaking-but-English-coding
  developer; the audience for generated audit output is the same person
  who already reads and writes code in English.
- **French-only generated content:** rejected, breaks consistency with
  the rest of the codebase and toolchain, which is entirely in English.
