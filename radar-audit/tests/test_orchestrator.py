import subprocess

from radar_audit.config import PortfolioConfig
from radar_audit.orchestrator import (
    AuditPlan,
    execute_audit,
    get_commit_sha,
    get_or_create_audit,
    is_dirty,
    plan_audit,
    resolve_repository,
)
from radar_audit.runner import RawToolOutput
from radar_core.models.audit import ToolResult
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


class _StubRunner:
    tool_name = "stub-runner"
    tool_version = "0.0.1"

    def run(self, subproject_path, exclude_paths):
        return RawToolOutput(
            command="stub",
            raw_output={"ok": True},
            exit_code=0,
            duration_ms=1,
        )


class _AlwaysCrashesRunner:
    tool_name = "crashes-runner"
    tool_version = "0.0.1"

    def run(self, subproject_path, exclude_paths):
        raise RuntimeError("boom")


def test_plan_audit_returns_repo_subprojects_and_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    plan = plan_audit(config, "repo")

    assert isinstance(plan, AuditPlan)
    assert plan.repository_name == "repo"
    assert plan.repository_path == repo_path.resolve()
    assert len(plan.subprojects) == 1
    assert plan.exclude_paths == []


def test_execute_audit_persists_one_tool_result_per_subproject_and_runner(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"backend/pyproject.toml": "[project]\nname='x'\n", "frontend/package.json": "{}\n"},
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_StubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert len(results) == 2
    assert all(r.tool_name == "stub-runner" for r in results)
    assert all(r.exit_code == 0 for r in results)


def test_execute_audit_continues_past_a_crashing_runner(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", [_AlwaysCrashesRunner(), _StubRunner()])

    results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert len(results) == 2

    crashed = next(r for r in results if r.tool_name == "crashes-runner")
    assert crashed.exit_code != 0
    assert "boom" in crashed.raw_output["error"]

    succeeded = next(r for r in results if r.tool_name == "stub-runner")
    assert succeeded.exit_code == 0


def test_plan_audit_excludes_worktrees_from_subprojects(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname='x'\n"})
    worktree_path = repo_path / "wt-feature"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    plan = plan_audit(config, "repo")

    worktree_resolved = worktree_path.resolve()
    assert not any(
        subproject.path == worktree_resolved or worktree_resolved in subproject.path.parents
        for subproject in plan.subprojects
    )


def test_execute_audit_replaces_tool_results_instead_of_accumulating_on_rerun(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    first_audit = execute_audit(db_session, config, "repo", [_StubRunner()])
    first_results = db_session.exec(
        select(ToolResult).where(ToolResult.audit_id == first_audit.id)
    ).all()

    second_audit = execute_audit(db_session, config, "repo", [_StubRunner()])
    second_results = db_session.exec(
        select(ToolResult).where(ToolResult.audit_id == second_audit.id)
    ).all()

    assert first_audit.id == second_audit.id
    assert len(second_results) == len(first_results)


def test_execute_audit_seeds_the_taxonomy(db_session, tmp_path):
    from radar_core.models.methodology import MethodologyVersion

    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    execute_audit(db_session, config, "repo", [_StubRunner()])

    version = db_session.exec(
        select(MethodologyVersion).where(
            MethodologyVersion.version_label == "Quality Framework v1.0"
        )
    ).first()
    assert version is not None
