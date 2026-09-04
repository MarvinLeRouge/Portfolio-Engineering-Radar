# Product context

> [Version française](product-context.fr.md) | English version

Minimal product-level context. For the full design rationale, see
[`docs/system-design.md`](system-design.md); for the audit criteria
themselves, see [`docs/quality-framework.md`](quality-framework.md).

## What this is

Portfolio Engineering Radar is a local, offline-first audit system for a
personal portfolio of software repositories. It runs a fixed set of
static-analysis and tooling checks against each repository, normalizes
the raw results into scored findings against the Quality Framework, and
is meant to feed a dashboard and a living improvement roadmap.

## Who it is for

A single developer auditing their own repositories. There is no
multi-tenant or multi-user concern: the audience is one person deciding
where to invest engineering-quality effort next across a portfolio of
projects.

## Why it exists

Manually tracking the technical health of many side projects does not
scale; findings get forgotten and quality drifts unevenly across repos.
The system exists to make that drift visible, comparable across repos,
and actionable through prioritized roadmap items, without requiring any
of the audited repositories to change anything about themselves.

## Current scope

- Audit engine (`radar-audit`) and data model (`radar-core`): in progress, see [`docs/roadmap.md`](roadmap.md)
- Dashboard and report generation: not started yet
