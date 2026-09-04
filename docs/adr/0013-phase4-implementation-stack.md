# 0013. Phase 4 implementation-level stack choices

**Status:** Accepted
**Date:** 2026-08-27
**Deciders:** Jean Ceugniet
**Sources:** PR #9 (`chore/phase-4-stack-decision`), commit 644d6e9

## Context

[0002](0002-dashboard-stack-and-launch.md) fixed the high-level stack
(Vue 3 + FastAPI + SQLite, `docker compose up`) but left several
implementation-level choices open before Phase 4 coding could start:
ORM/data-modeling approach, migration tooling, frontend state management,
and repository layout.

## Decision

- **Backend:** Python 3.12, dependency management via `uv` (consistent
  with the tooling already standardized across target repos, e.g.
  GeoChallenge-Tracker). ORM: **SQLModel** (SQLAlchemy + Pydantic fused)
  over separate SQLAlchemy/Pydantic layers, to avoid duplicating roughly
  13 data-model entities across two representations, acceptable given
  the project is local-first and mono-developer. Migrations via
  **Alembic**. Tests via **pytest**. Pre-commit: `ruff` + `ruff-format` +
  `mypy`, dogfooding the pre-commit criterion
  ([0009](0009-precommit-quality-gate-criterion.md)) this very system
  audits elsewhere.
- **Frontend:** Vue 3 + Vite + TypeScript, **Pinia** (state) + **Vue
  Router**, tests via **vitest**, pre-commit: `eslint` + `prettier` +
  `vue-tsc`. CSS: **Tailwind**.
- **Traefik in front of `radar-api`/`radar-dashboard`:** applied for
  consistency with the portfolio-wide Traefik standard
  ([0008](0008-traefik-criterion-and-confirmation-gate.md)), even though
  remote exposure of this tool is unlikely. Deliberate choice, not a
  default.
- **Repo structure:** monorepo, sibling folders `radar-audit/`,
  `radar-api/`, `radar-dashboard/` at the root, alongside the existing
  `docs/`.

## Consequences

- `radar-core`'s data model is defined once as SQLModel classes and
  reused directly for both database access and API schemas, rather than
  maintained as parallel SQLAlchemy models and Pydantic schemas.
- The workspace is a single `uv` monorepo (`radar-core` + `radar-audit`
  so far; `radar-api`/`radar-dashboard` to follow the same layout), not
  separate repositories per component.
- Frontend and backend pre-commit gates dogfood the exact criterion the
  system audits in every other portfolio repository.

## Alternatives considered

- **Separate SQLAlchemy models and Pydantic schemas:** rejected, would
  double the maintenance surface of the data model for a single-developer
  project with no need for that layering's usual benefits (independent
  API/DB evolution at scale).
- **Split each component into its own repository:** rejected in favor of
  a monorepo, simpler to coordinate for a single developer building
  tightly coupled components.
