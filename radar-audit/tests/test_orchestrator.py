from radar_audit.orchestrator import (
    get_commit_sha,
    get_or_create_audit,
    is_dirty,
    resolve_repository,
)
from radar_core.models.repository import Repository
from sqlmodel import select

from tests.git_helpers import init_git_repo


def test_resolve_repository_creates_a_new_repository(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    repository = resolve_repository(db_session, repo_path, "repo")

    assert repository.id is not None
    assert repository.name == "repo"
    assert repository.path == str(repo_path)


def test_resolve_repository_reuses_existing_by_path(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    first = resolve_repository(db_session, repo_path, "repo")
    second = resolve_repository(db_session, repo_path, "repo")

    assert first.id == second.id
    all_repos = db_session.exec(select(Repository).where(Repository.path == str(repo_path))).all()
    assert len(all_repos) == 1


def test_get_commit_sha_returns_head_sha(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    sha = get_commit_sha(repo_path)

    assert len(sha) == 40


def test_is_dirty_false_on_clean_checkout(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert is_dirty(repo_path) is False


def test_is_dirty_true_with_uncommitted_changes(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})
    (repo_path / "README.md").write_text("modified\n")

    assert is_dirty(repo_path) is True


def test_get_or_create_audit_creates_a_new_audit(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    repository = resolve_repository(db_session, repo_path, "repo")

    audit = get_or_create_audit(db_session, repository)

    assert audit.id is not None
    assert audit.repository_id == repository.id
    assert audit.is_dirty is False


def test_get_or_create_audit_reuses_existing_clean_commit_audit(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    repository = resolve_repository(db_session, repo_path, "repo")

    first = get_or_create_audit(db_session, repository)
    second = get_or_create_audit(db_session, repository)

    assert first.id == second.id


def test_get_or_create_audit_creates_a_new_row_per_dirty_run(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})
    (repo_path / "README.md").write_text("modified\n")
    repository = resolve_repository(db_session, repo_path, "repo")

    first = get_or_create_audit(db_session, repository)
    second = get_or_create_audit(db_session, repository)

    assert first.id != second.id
