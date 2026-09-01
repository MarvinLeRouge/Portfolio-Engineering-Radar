from __future__ import annotations

import os
from pathlib import Path
from subprocess import CalledProcessError

import typer
from radar_core.db import get_engine, get_session

from radar_audit.config import PortfolioConfigError, load_portfolio_config
from radar_audit.orchestrator import AuditPlan, execute_audit, plan_audit, planned_runs
from radar_audit.runner import ToolRunner
from radar_audit.runners.ci_workflow_runner import CiWorkflowRunner
from radar_audit.runners.dependency_cruiser_runner import DependencyCruiserRunner
from radar_audit.runners.design_doc_runner import DesignDocRunner
from radar_audit.runners.eslint_complexity_runner import EslintComplexityRunner
from radar_audit.runners.eslint_lint_runner import EslintLintRunner
from radar_audit.runners.integration_test_runner import IntegrationTestRunner
from radar_audit.runners.jscpd_runner import JscpdRunner
from radar_audit.runners.mypy_runner import MypyRunner
from radar_audit.runners.pest_runner import PestRunner
from radar_audit.runners.phpmd_complexity_runner import PhpmdComplexityRunner
from radar_audit.runners.phpstan_runner import PhpstanRunner
from radar_audit.runners.pint_runner import PintRunner
from radar_audit.runners.playwright_presence_runner import PlaywrightPresenceRunner
from radar_audit.runners.precommit_gate_runner import PreCommitGateRunner
from radar_audit.runners.pydeps_runner import PydepsRunner
from radar_audit.runners.pytest_coverage_runner import PytestCoverageRunner
from radar_audit.runners.radon_complexity_runner import RadonComplexityRunner
from radar_audit.runners.radon_module_size_runner import RadonModuleSizeRunner
from radar_audit.runners.ruff_runner import RuffRunner
from radar_audit.runners.static_loc_runner import StaticLocRunner
from radar_audit.runners.typescript_runner import TypeScriptRunner
from radar_audit.runners.vitest_runner import VitestRunner

app = typer.Typer()

DEFAULT_PORTFOLIO_YAML = Path(__file__).resolve().parents[2] / "portfolio.yaml"
DEFAULT_RUNNERS: list[ToolRunner] = [
    DependencyCruiserRunner(),
    PydepsRunner(),
    DesignDocRunner(),
    RadonModuleSizeRunner(),
    StaticLocRunner(),
    RuffRunner(),
    EslintLintRunner(),
    PintRunner(),
    MypyRunner(),
    TypeScriptRunner(),
    PhpstanRunner(),
    RadonComplexityRunner(),
    EslintComplexityRunner(),
    PhpmdComplexityRunner(),
    PreCommitGateRunner(),
    JscpdRunner(),
    PytestCoverageRunner(),
    VitestRunner(),
    PestRunner(),
    IntegrationTestRunner(),
    CiWorkflowRunner(),
    PlaywrightPresenceRunner(),
]


class MissingDatabaseUrlError(RuntimeError):
    """Raised when RADAR_DATABASE_URL is not set for a real (non-dry-run) audit."""


def _database_url() -> str:
    url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        raise MissingDatabaseUrlError(
            "RADAR_DATABASE_URL must be set explicitly; radar-audit never assumes "
            "a default database location."
        )
    return url


_EXPECTED_ERRORS = (
    MissingDatabaseUrlError,
    PortfolioConfigError,
    FileNotFoundError,
    CalledProcessError,
)


@app.callback(invoke_without_command=True)
def main() -> None:
    """Radar-audit: tool orchestration engine for Portfolio-Engineering-Radar."""
    pass


@app.command()
def run(
    repo_name: str | None = typer.Argument(None, help="Repository name from portfolio.yaml"),
    all_repos: bool = typer.Option(False, "--all", help="Audit every repository in portfolio.yaml"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the audit plan without executing anything"
    ),
    config_path: Path = typer.Option(  # noqa: B008
        DEFAULT_PORTFOLIO_YAML, "--config", help="Path to portfolio.yaml"
    ),
) -> None:
    if not all_repos and repo_name is None:
        raise typer.BadParameter("Provide a repository name or use --all")

    try:
        config = load_portfolio_config(config_path)
        if all_repos:
            repo_names = config.repositories
        else:
            assert repo_name is not None  # Guaranteed by the check above
            repo_names = [repo_name]

        if dry_run:
            for name in repo_names:
                _print_plan(plan_audit(config, name))
            return

        engine = get_engine(_database_url())
        session = get_session(engine)
        try:
            for name in repo_names:
                execute_audit(session, config, name, DEFAULT_RUNNERS)
        finally:
            session.close()
            engine.dispose()
    except _EXPECTED_ERRORS as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc


def _print_plan(plan: AuditPlan) -> None:
    typer.echo(f"Repository: {plan.repository_name} ({plan.repository_path})")
    typer.echo(f"Excluded worktrees: {[str(p) for p in plan.exclude_paths]}")
    for subproject in plan.subprojects:
        typer.echo(f"  subproject: {subproject.path} [{subproject.stack}]")
    for run in planned_runs(plan, DEFAULT_RUNNERS):
        typer.echo(f"  {run.target_path}: would run: {run.runner.tool_name}")


if __name__ == "__main__":
    app()
