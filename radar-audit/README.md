# radar-audit

> [Version française](README.fr.md) | English version

Tool orchestration and normalization engine for [Portfolio-Engineering-Radar](../README.md).

`radar-audit` discovers a repository's sub-projects, runs the deterministic
analysis tools relevant to each detected stack, and persists their raw
results against the versioned Quality Framework taxonomy. See
[`docs/quality-framework.md`](../docs/quality-framework.md) for the full
methodology and [`docs/toolchain.md`](../docs/toolchain.md) for how each
tool was selected.

## Coverage

Currently wired: 22 tool runners across Quality Framework categories 1-3.

| Category | Criteria covered | Tools |
|---|---|---|
| 1. Architecture & design | dependency circularity, design-doc presence, module size | dependency-cruiser, pydeps, radon, static LOC walk |
| 2. Code quality | lint pass rate, type-check pass rate, cyclomatic complexity, pre-commit quality gate, code duplication | Ruff, ESLint, Pint, mypy, tsc, PHPStan, Radon, PHPMD, jscpd |
| 3. Testing & reliability | unit test pass rate + coverage, integration tests, E2E tests, CI test execution | pytest-cov, Vitest, Pest, GitHub Actions workflow inspection, Playwright presence |

Categories 4-15 are not implemented yet; see [`docs/roadmap.md`](../docs/roadmap.md).

## Prerequisites

`radar-audit` writes to the same SQLite database as `radar-core`'s Alembic
migrations. Before running a real (non-dry-run) audit for the first time,
apply the migrations against the target database:

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Usage

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-audit radar-audit run <repo-name>
    uv run --package radar-audit radar-audit run --all
    uv run --package radar-audit radar-audit run <repo-name> --dry-run

`--dry-run` prints the discovered sub-projects and the tools that would run,
without touching the database.

Repository scope and the local checkout root are configured in
`portfolio.yaml` (versioned in this directory).
