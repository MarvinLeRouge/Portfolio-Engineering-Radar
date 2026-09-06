[🇫🇷 Version française](architecture.fr.md) | 🇬🇧 English version

---

# Architecture - Portfolio Engineering Radar

> Public technical reference. See [radar-core architecture](architecture/radar-core_architecture.md) and [radar-audit architecture](architecture/radar-audit_architecture.md) for implementation details.

## Overview

Portfolio Engineering Radar audits a portfolio of local repositories against a versioned Quality Framework, storing results in a shared data model:

- **`radar-core`** - shared SQLModel data model and Alembic migration history. No orchestration logic of its own; every other component reads and writes against it.
- **`radar-audit`** - one-shot CLI (`radar-audit run ...`) that discovers sub-projects, runs pinned external tools per detected stack with crash isolation, and normalizes raw tool output into `Finding`/`Score` rows against the frozen taxonomy.
- **`radar-api` / `radar-dashboard`** (planned) - FastAPI read/write API and Vue 3 SPA consuming it, not yet implemented.

## Project structure

```
portfolio-engineering-radar/
├── radar-core/
│   └── src/radar_core/
│       ├── db.py         # engine/session helpers
│       ├── enums.py       # shared enum types
│       ├── types.py       # UTCDateTime column type
│       └── models/        # Repository, Audit, Finding, Score, Roadmap, ...
├── radar-audit/
│   └── src/radar_audit/
│       ├── config.py       # portfolio.yaml loading/validation
│       ├── discovery.py     # sub-project detection per manifest file
│       ├── worktree.py       # exclude-path computation
│       ├── orchestrator.py    # Repository/Audit resolution, AuditPlan execution
│       ├── runner.py           # ToolRunner protocol
│       ├── runners/             # one ToolRunner per external tool
│       ├── normalizers/          # raw_output -> Finding/Score, per criterion
│       └── taxonomy/seed.py       # Quality Framework taxonomy seeding
└── docs/
    ├── architecture/    # radar-core/radar-audit architecture
    ├── adr/             # architecture decision records
    └── guides/          # developer guide
```

## Further reading

- [radar-core architecture](architecture/radar-core_architecture.md)
- [radar-audit architecture](architecture/radar-audit_architecture.md)
- [Quality Framework](quality-framework.md)
- [Toolchain](toolchain.md)
- [Architecture decision records](adr/README.md)
- [Developer guide](guides/developer_guide.md)
- [Product context](product-context.md)
- [Operations](operations.md)
