# 0012. External network access for dependency freshness checks

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #3 (`chore/phase-1-toolchain-discovery`), commit c2b1e8b

## Context

Raised during Phase 1 toolchain evaluation of the Security domain:
`pip-audit`/`pnpm audit`/`composer audit` only detect known CVEs on
pinned versions, not staleness (a dependency several majors behind, or
abandoned, with no CVE filed). Checking freshness
(`pip list --outdated`, `npm outdated`/`pnpm outdated`, `composer
outdated`) requires querying the relevant package registry (PyPI, npm,
Packagist) for the latest available version, a network dependency
distinct from the GitHub API access covered by
[0003](0003-github-api-network-access.md).

## Decision

Allow read-only access to public package registries (PyPI, npm,
Packagist) to check dependency freshness, opt-in per run (same mechanism
as [0003](0003-github-api-network-access.md), e.g.
`--allow-registry-lookup`), not enabled by default. No authentication, no
write scope. Feeds category 11 (Dependency management), whose detailed
criteria are still deferred per
[0005](0005-taxonomy-adjustments-deferred.md).

## Consequences

- Dependency-freshness criteria are unavailable unless the operator
  explicitly opts in for that run, consistent with the local-first
  default.
- The audit system now has two independently gated network-access flags
  (GitHub API, package registries), each opt-in on its own, so an
  operator can enable one without the other.

## Alternatives considered

- **Reuse the same `--allow-github-api` flag for registry lookups:**
  rejected, the two data sources are unrelated and an operator may want
  one without the other.
- **Rely only on CVE-based checks, skip freshness entirely:** rejected,
  loses a real signal (silently unmaintained or badly outdated
  dependencies with no filed CVE).
