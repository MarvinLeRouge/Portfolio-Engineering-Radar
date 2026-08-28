from __future__ import annotations

import subprocess
from pathlib import Path

from radar_core.models.audit import Audit
from radar_core.models.repository import Repository
from sqlmodel import Session, select


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
