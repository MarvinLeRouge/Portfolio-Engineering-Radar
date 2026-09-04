# 0004. Toolchain installation strategy

**Status:** Accepted
**Date:** 2026-08-26
**Deciders:** Jean Ceugniet
**Sources:** PR #2 (`chore/initalize-project`), commit 5537efe

## Context

No analysis tool (Semgrep, Ruff, ESLint, PHPStan, Trivy, etc.) is
installed globally on the development machine. Relying on whichever
version of a linter/type-checker a target repository happens to declare
in its own `devDependencies` would make audit scores drift with the
target repo's own tooling choices, breaking score stability across
audits.

## Decision

The audit system pins and runs its own tool versions ephemerally (`uvx`,
`pnpm dlx`/`npx`, isolated Composer installs, or containers), independent
of what each target repo declares. "Ephemeral" means not persistently
installed in the global system environment (not in `PATH`, isolated per
pinned version), not "re-downloaded on every run": the first invocation
of a given pinned version downloads and caches it locally (e.g.
`~/.cache/uv`, npx cache), subsequent invocations reuse the cache.

## Consequences

- Score changes between audits reflect real changes in the target
  repository, not a silent upgrade of a linter the target repo happened
  to bump.
- The audit system carries the maintenance burden of pinning and
  periodically updating its own toolchain, tracked in
  [`docs/toolchain.md`](../toolchain.md).
- Tool invocations must be structured so a per-tool version pin is easy
  to change without touching runner logic.

## Alternatives considered

- **Use each target repo's own installed tool versions:** rejected, this
  is exactly the score-stability risk this decision exists to avoid.
- **Install every tool globally on the audit machine:** rejected, harder
  to reproduce, version-pin, or run in a container, and conflicts with
  the local-first, ephemeral-tooling approach.
