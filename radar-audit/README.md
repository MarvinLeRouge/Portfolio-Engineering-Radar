# radar-audit

Tool orchestration and normalization engine for Portfolio-Engineering-Radar.

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
