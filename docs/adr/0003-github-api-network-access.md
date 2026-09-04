# 0003. External network access for certain criteria (GitHub API)

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

Some potentially valuable criteria require the GitHub API (branch
protection rules, PR review requirements, Actions run history beyond
what's available in the local `.git`). This conflicts with the
local-first principle governing the audit system unless explicitly
opted into.

## Decision

Allow GitHub API access, **read-only** (repos, commits, PRs, never write
scope), gated behind an explicit per-run opt-in (e.g. `--allow-github-api`),
not enabled by default. Remote-fetched evidence is tagged distinctly from
local static evidence (`.git`) in the data model.

## Consequences

- Any criterion depending on the GitHub API is unavailable unless the
  operator explicitly opts in for that run.
- The data model must distinguish evidence provenance (local vs. remote)
  so scores stay reproducible and explainable when the flag is off.
- No GitHub write scope is ever requested, ruling out any criterion that
  would require the audit tool to modify a repository's GitHub-side
  configuration.

## Alternatives considered

- **Always query the GitHub API:** rejected, breaks the local-first,
  fully offline default behavior expected of the tool.
- **Never support GitHub API-backed criteria:** rejected, would
  permanently exclude criteria (e.g. branch protection) with real
  engineering-quality signal.
