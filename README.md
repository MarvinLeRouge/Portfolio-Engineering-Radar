# Portfolio Engineering Radar

> Evidence-based, AI-assisted quality monitoring and continuous improvement for software portfolios.

**Portfolio Engineering Radar** is a local-first engineering quality platform designed to assess, compare, prioritize, and continuously improve a portfolio of software projects.

The project is being designed for a fullstack web developer working across multiple repositories and technology stacks. Its purpose is not to replace engineering judgment with an AI-generated score, but to combine deterministic analysis tools, evidence-based assessment, a versioned quality framework, and AI-assisted reasoning into a coherent improvement system.

## Project vision

Managing several applications creates a problem that is difficult to solve repository by repository: individual projects can improve while the portfolio as a whole remains inconsistent.

Portfolio Engineering Radar aims to provide a continuous loop:

```text
Repositories
     ↓
Automated analysis
     ↓
Evidence
     ↓
Quality assessment
     ↓
Prioritization
     ↓
Roadmap
     ↓
Implementation
     ↓
Re-audit
     ↺
```

The system should make it possible to answer:

- What is the current quality of each repository?
- What is the overall state of the portfolio?
- Which problems are shared by several projects?
- What should be fixed first?
- What is the expected impact versus effort?
- Is the roadmap still representative of the actual codebase?
- Is engineering quality genuinely improving over time?

## Core principles

### Evidence before scoring

Scores must be supported by observable evidence whenever possible. Deterministic tools should provide measurements and findings; AI should primarily interpret, correlate, prioritize, and explain them.

### Versioned quality methodology

The categories, criteria, rules, weights, scoring model, and confidence model must be explicitly defined and versioned.

A score obtained today must remain meaningfully comparable with a score obtained later. Changes to the methodology must therefore be tracked and must never silently alter historical measurements.

### Portfolio-level thinking

The objective is not to make every repository technically identical.

The system should identify where engineering principles can be standardized while preserving legitimate differences between stacks, architectures, and domains.

### Roadmap as a living representation

The roadmap is not a static planning document. It must reflect the actual state of the repositories, be updated after audits and implementation work, and provide a traceable relationship between findings, improvements, and validation.

### Local-first

Repositories are available locally. The system should prioritize local analysis and avoid transmitting source code or secrets to external services unnecessarily.

### Continuous reassessment

An improvement is not considered complete merely because code was changed. The system should be able to re-audit the affected criteria and provide evidence that the expected improvement actually occurred.

## Planned capabilities

- Multi-repository analysis
- Common engineering quality framework
- Versioned scoring methodology
- Evidence-based findings
- Static analysis and security tooling integration
- Architecture and maintainability assessment
- Testing and reliability assessment
- Security assessment
- CI/CD and developer-experience assessment
- Technical debt tracking
- Cross-project analysis
- Prioritized improvement backlog
- Living roadmap
- Historical quality snapshots
- Portfolio quality trends
- Local dashboard
- AI-assisted analysis and planning
- Self-auditing of Portfolio Engineering Radar itself

## Target environment

The initial system is intended for a fullstack web developer working primarily with technologies such as:

- Vue.js / Vue 3
- Python / FastAPI
- PHP / Laravel
- MongoDB and SQL databases
- Docker / Docker Compose
- Git / GitHub
- GitHub Actions

The architecture should remain technology-aware without making the quality model dependent on a particular stack.

## Development approach

The project will be developed in explicit stages:

1. Define the system architecture and quality methodology.
2. Discover and evaluate the optimal analysis toolchain.
3. Define and version the complete categories, criteria, rules, weights, and scoring system.
4. Calibrate the framework against a pilot repository.
5. Implement the audit and data model.
6. Implement the local dashboard.
7. Audit the portfolio.
8. Build and maintain the improvement roadmap.
9. Re-audit continuously and measure actual progress.

The methodology must be established before the first full portfolio assessment.

## Status

**Early design / architecture phase.**

The first milestone is to establish a rigorous and reproducible foundation before implementing the dashboard or running a complete portfolio audit.

## Documentation

Documentation will progressively cover:

- system architecture
- quality framework
- scoring model
- toolchain selection
- audit methodology
- roadmap
- architectural decisions

## Language

- [English README](README.md)
- [Documentation française](README.fr.md)

## License

License to be defined.
