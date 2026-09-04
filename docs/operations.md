# Operations

> [Version française](operations.fr.md) | English version

Minimal operations reference. This is a local, single-user, offline-first
system: there is no hosted deployment yet.

## Running the audit engine

`radar-audit` is invoked manually as a CLI command; it is not a
long-running service. See the [developer guide](guides/developer_guide.md)
for setup and usage.

## Data

All structured audit data lives in the database pointed to by
`RADAR_DATABASE_URL`. For local use this is typically a gitignored SQLite
file; nothing about the schema assumes SQLite specifically (managed via
Alembic migrations in `radar-core`).

Raw tool output captured during a run is kept alongside the normalized
results rather than discarded, so a finding can always be traced back to
the tool invocation that produced it.

There is no backup automation yet: back up the database file manually if
its contents matter to you (for example before running a destructive
migration).

## CI / automation

- `CHANGELOG.md` is regenerated automatically on every push to `main` via [`.github/workflows/changelog.yml`](../.github/workflows/changelog.yml) (opens a pull request, does not push directly to `main`)
- There is no CI pipeline yet running tests or the `ruff`/`mypy` gates remotely; these run locally via pre-commit hooks (see [`CONTRIBUTING.md`](../CONTRIBUTING.md)). Tracked in [`docs/roadmap.md`](roadmap.md)

## Secrets

The audit engine reads local repositories read-only and does not require
any credentials or API keys for its current scope. If a future criterion
needs network access or an API key, it must be opt-in and explicitly
flagged (see the network-access decision in [`docs/adr/`](adr/)).
