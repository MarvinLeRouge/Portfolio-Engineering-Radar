from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository
from sqlmodel import Session, select

from radar_audit.config import PortfolioConfig
from radar_audit.discovery import SubProject, discover_subprojects
from radar_audit.runner import RawToolOutput, ToolRunner
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_audit.worktree import compute_exclude_paths


def resolve_repository(session: Session, repo_path: Path, repo_name: str) -> Repository:
    existing = session.exec(select(Repository).where(Repository.path == str(repo_path))).first()
    if existing is not None:
        return existing

    repository = Repository(name=repo_name, path=str(repo_path))
    session.add(repository)
    session.commit()
    session.refresh(repository)
    return repository


def get_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def is_dirty(repo_path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def get_or_create_audit(session: Session, repository: Repository) -> Audit:
    """Create an Audit for the repo's current HEAD, reusing an existing one for the same
    clean commit (the DB enforces at most one clean-commit Audit per repo via a unique
    index — see radar_core/src/radar_core/models/audit.py). Every dirty-checkout run gets
    its own new Audit row, since dirty state isn't reproducible/comparable across runs.
    """
    repo_path = Path(repository.path)
    commit_sha = get_commit_sha(repo_path)
    dirty = is_dirty(repo_path)

    if not dirty:
        existing = session.exec(
            select(Audit).where(
                Audit.repository_id == repository.id,
                Audit.commit_sha == commit_sha,
                Audit.is_dirty.is_(False),  # type: ignore[attr-defined]
            )
        ).first()
        if existing is not None:
            return existing

    audit = Audit(repository_id=repository.id, commit_sha=commit_sha, is_dirty=dirty)
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit


@dataclass(frozen=True)
class AuditPlan:
    repository_name: str
    repository_path: Path
    subprojects: list[SubProject]
    exclude_paths: list[Path]


def plan_audit(config: PortfolioConfig, repo_name: str) -> AuditPlan:
    repo_path = config.resolve_repo_path(repo_name)
    exclude_paths = compute_exclude_paths(repo_path)
    subprojects = [
        subproject
        for subproject in discover_subprojects(repo_path)
        if not _is_excluded(subproject.path, exclude_paths)
    ]
    return AuditPlan(
        repository_name=repo_name,
        repository_path=repo_path,
        subprojects=subprojects,
        exclude_paths=exclude_paths,
    )


def _is_excluded(path: Path, exclude_paths: list[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == excluded or excluded in resolved.parents for excluded in exclude_paths)


@dataclass(frozen=True)
class PlannedRun:
    target_path: Path
    runner: ToolRunner


def planned_runs(plan: AuditPlan, runners: list[ToolRunner]) -> list[PlannedRun]:
    """The exact (target_path, runner) pairs execute_audit will invoke -- shared
    with the CLI's --dry-run preview so the two never drift out of sync (a
    repo-scope runner runs once per audit; a subproject-scope runner runs
    once per matching-stack physical target, even when several subprojects
    at the same path differ only by stack -- e.g. a PHP + JS monorepo with
    no folder separation).
    """
    runs: list[PlannedRun] = []
    repo_scope_done: set[str] = set()
    subproject_scope_done: set[tuple[Path, str]] = set()
    for subproject in plan.subprojects:
        for runner in runners:
            if runner.scope == "repo":
                if runner.tool_name in repo_scope_done:
                    continue
                repo_scope_done.add(runner.tool_name)
                runs.append(PlannedRun(plan.repository_path, runner))
            else:
                if subproject.stack not in runner.supported_stacks:
                    continue
                key = (subproject.path, runner.tool_name)
                if key in subproject_scope_done:
                    continue
                subproject_scope_done.add(key)
                runs.append(PlannedRun(subproject.path, runner))
    return runs


def execute_audit(
    session: Session,
    config: PortfolioConfig,
    repo_name: str,
    runners: list[ToolRunner],
) -> Audit:
    plan = plan_audit(config, repo_name)

    seed_taxonomy(session)
    repository = resolve_repository(session, plan.repository_path, repo_name)
    audit = get_or_create_audit(session, repository)

    existing_results = session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    for result in existing_results:
        session.delete(result)

    for run in planned_runs(plan, runners):
        raw = _run_tool_safely(run.runner, run.target_path, plan.exclude_paths)
        session.add(
            ToolResult(
                audit_id=audit.id,
                subproject_path=_relative_subproject_path(run.target_path, plan.repository_path),
                tool_name=run.runner.tool_name,
                tool_version=run.runner.tool_version,
                command=raw.command,
                raw_output=raw.raw_output,
                exit_code=raw.exit_code,
                duration_ms=raw.duration_ms,
            )
        )

    session.commit()
    session.refresh(audit)
    return audit


def _relative_subproject_path(target_path: Path, repository_path: Path) -> str:
    resolved_target = target_path.resolve()
    resolved_repo = repository_path.resolve()
    if resolved_target == resolved_repo:
        return "."
    return str(resolved_target.relative_to(resolved_repo))


def _run_tool_safely(
    runner: ToolRunner, target_path: Path, exclude_paths: list[Path]
) -> RawToolOutput:
    try:
        return runner.run(target_path, exclude_paths)
    except Exception as exc:  # noqa: BLE001 - a tool crash must persist as evidence, never abort the audit
        return RawToolOutput(
            command=f"{runner.tool_name} (crashed)",
            raw_output={"error": str(exc)},
            exit_code=-1,
            duration_ms=0,
        )
