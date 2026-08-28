from __future__ import annotations

import os
from pathlib import Path

import typer
from radar_core.db import get_engine, get_session

from radar_audit.config import load_portfolio_config
from radar_audit.orchestrator import AuditPlan, execute_audit, plan_audit
from radar_audit.runner import ToolRunner
from radar_audit.runners.example import ExampleGitLogRunner

app = typer.Typer()

DEFAULT_PORTFOLIO_YAML = Path(__file__).resolve().parents[2] / "portfolio.yaml"
DEFAULT_RUNNERS: list[ToolRunner] = [ExampleGitLogRunner()]


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


def _print_plan(plan: AuditPlan) -> None:
    typer.echo(f"Repository: {plan.repository_name} ({plan.repository_path})")
    typer.echo(f"Excluded worktrees: {[str(p) for p in plan.exclude_paths]}")
    for subproject in plan.subprojects:
        typer.echo(f"  subproject: {subproject.path} [{subproject.stack}]")
        for tool_runner in DEFAULT_RUNNERS:
            typer.echo(f"    would run: {tool_runner.tool_name}")


if __name__ == "__main__":
    app()
