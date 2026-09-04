# 0002. Dashboard stack and launch mechanism

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

The original design proposal suggested Vue 3 + FastAPI + SQLite,
optionally launched behind `docker compose up`, without settling whether
containerization would cover the audit engine itself or only the
dashboard services.

## Decision

Full containerization via `docker compose up`, including `radar-audit`
alongside `radar-api`/`radar-dashboard`, not just the two dashboard
services. Chosen deliberately for environment control, even though the
tool has no deployment target of its own and runs on a single machine for
a single user.

## Consequences

- Every component, including the CLI-driven audit engine, must run
  correctly inside a container, not just the long-running services.
- Local development requires Docker even though the system is
  single-user and single-machine; this trades a small amount of local
  friction for consistent, reproducible environments across the whole
  stack.

## Alternatives considered

- **Containerize only `radar-api`/`radar-dashboard`, run `radar-audit`
  natively:** rejected in favor of full consistency, since running the
  audit engine outside the container would reintroduce the
  environment-drift risk the containerization was meant to remove.
