# radar-audit architecture

> [Version française](radar-audit_architecture.fr.md) | English version

`radar-audit` orchestrates tool execution against a repository and
normalizes the raw results into the `radar-core` data model. It is
invoked as a one-shot CLI command (`radar-audit run ...`), not a
long-running service, and never mutates the audited repository.

## Pipeline

```text
portfolio.yaml
    ↓
PortfolioConfig (config.py)
    ↓
resolve_repository / get_or_create_audit (orchestrator.py)
    ↓
discover_subprojects (discovery.py)         compute_exclude_paths (worktree.py)
    ↓                                              ↓
plan_audit → AuditPlan (subprojects × exclude_paths)
    ↓
planned_runs (AuditPlan × DEFAULT_RUNNERS, filtered by stack/scope)
    ↓
execute_audit: each ToolRunner.run() invoked with crash isolation
    ↓
ToolResult rows (raw_output preserved as-is)
    ↓
normalizers/*.py: raw_output → Finding / Score, per Quality Framework criterion
```

## Responsibilities

- **`config.py`**: loads and validates `portfolio.yaml` (`repos_root` + repository list); raises `PortfolioConfigError` rather than failing silently on a malformed config.
- **`discovery.py`**: detects sub-projects inside a repository by manifest file (`pyproject.toml`/`requirements.txt` -> python, `package.json` -> javascript, `composer.json` -> php), one level deep plus the repo root itself; falls back to a single `unknown`-stack sub-project when no manifest is found.
- **`worktree.py`**: computes the list of paths to exclude from analysis, derived from `git worktree list`, so nested worktrees are never double-counted by tools like coverage or duplication runners.
- **`orchestrator.py`**: resolves the `Repository`/`Audit` rows (keyed on `commit_sha`, reused on re-run against an unchanged commit), builds the `AuditPlan`, filters runners by `stack`/`scope`, and executes each run with per-tool crash isolation so one failing tool never aborts the whole audit.
- **`runner.py`**: defines the `ToolRunner` protocol (`tool_name`, `tool_version`, `supported_stacks`, `scope`, `timeout_s`, `run()`) that every tool integration implements, and the `RawToolOutput` dataclass every `run()` returns.
- **`runners/`**: one `ToolRunner` implementation per external tool (dependency-cruiser, pydeps, ruff, mypy, ESLint, TypeScript, PHPStan, Pint, radon, phpmd, jscpd, pytest, Vitest, Pest, pre-commit, CI workflow presence, Playwright presence, and design-doc presence).
- **`normalizers/`**: one function per criterion, mapping a `ToolResult.raw_output` (or a set of them) to a `Finding`/`Score` against a specific Quality Framework criterion.
- **`taxonomy/seed.py`**: idempotently seeds the Quality Framework v1.0 taxonomy (`MethodologyVersion`/`Category`/`Criterion` rows) from a YAML source of truth, so the taxonomy in the database always matches the frozen methodology document.
- **`cli.py`**: the Typer entrypoint (`radar-audit run <repo>|--all [--dry-run] [--config path]`), wiring the pipeline above to a `radar-core` session and registering `DEFAULT_RUNNERS`.

## Key design decisions

- **Crash isolation per tool.** A runner that crashes or times out produces a failed `ToolResult` rather than aborting the audit; every other runner still executes.
- **Stack/scope filtering happens at planning time.** `planned_runs()` cross-references each sub-project's detected stack against each runner's `supported_stacks`, and its `scope` (`repo` vs `subproject`) against the sub-project layout, so language-specific tools never run against the wrong stack.
- **Worktrees are excluded globally**, not per-runner: `compute_exclude_paths` runs once per audit and its result is threaded into every tool invocation that accepts an exclude list, since several early runners independently double-counted nested worktree files before this was centralized.
- **`--dry-run` never touches the database or invokes any external tool**; it only prints the resolved plan, which makes it safe to use for debugging `portfolio.yaml` or stack detection.
- **Never assumes a database location.** `RADAR_DATABASE_URL` must be set explicitly for any non-dry-run invocation; see [`docs/operations.md`](../operations.md#secrets) for the reasoning.

## Adding a new normalization increment

See the ["Adding a new tool runner"](../guides/developer_guide.md#adding-a-new-tool-runner) section of the developer guide for the concrete steps.
