# 0001. Portfolio scope: which repositories are audited

**Status:** Accepted
**Date:** 2026-08-25
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

An inventory of the local development environment found 20 repositories.
Not all of them are relevant to an engineering-quality audit: some are
duplicates or stale clones, one holds personal data with no engineering
content, and the audit tool itself needed an explicit decision on whether
to include itself.

## Decision

Confirmed portfolio scope (10 repositories): CC-Beacon,
GeoChallenge-Tracker, HexaRot, HiveMind, JobFlow, Stamped, Summit-Stats,
Trello-Board-Init, Triton, and **Portfolio-Engineering-Radar itself**
(self-audit, included from the start, not deferred).

All other repositories are out of scope: laravel-task-manager,
laravel-task-manager-api, MarvinLeRouge.dev Homepage, MarvinLeRouge-github,
PlayWithPi, project-templates, Recherche emploi, Summit-Stats-clean, temp,
Training.

### Resolution notes folded into this decision

- **Duplicate/stale repositories:** `Summit-Stats-clean` and `temp` both
  point to the same remote as `Summit-Stats` and have older last-commit
  dates. They are stale local clones rather than intentional forks, and
  are excluded by the scope above.
- **Sensitive repository ("Recherche emploi"):** contains personal data
  (CVs, job-application tracking, personal notes) with no engineering
  content to audit. Excluded, consistent with the source-minimization
  principle.
- **CC-Beacon's status:** the developer's own session-tracking tool
  (FastAPI + web), which ships a `docker-compose.prod.yml` targeting an
  external VPS. Included in scope, but the audit must never contact that
  VPS: local-only static/deterministic checks only.

## Consequences

- The audit engine's `portfolio.yaml` is scoped to exactly these 10
  repositories; adding a repository to the portfolio requires an explicit
  edit, not automatic discovery of every local repository.
- CC-Beacon's runners must never perform network calls against its
  production VPS; this constrains which tools/checks can apply to it.
- Excluding "Recherche emploi" means the audit system never processes
  files containing personal data, simplifying the confidentiality surface.

## Alternatives considered

- **Audit every local repository automatically:** rejected, since it
  would pull in duplicate clones, personal-data repositories, and
  unrelated experiments, diluting the audit's signal and creating a
  privacy risk.
- **Exclude Portfolio-Engineering-Radar from its own audit:** rejected;
  self-auditing was considered valuable dogfooding and was included from
  the start rather than deferred to a later phase.
