import subprocess

from radar_audit.worktree import compute_exclude_paths

from tests.git_helpers import init_git_repo


def test_repo_with_no_extra_worktrees_returns_empty_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert compute_exclude_paths(repo_path) == []


def test_repo_with_a_worktree_excludes_it(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert result == [worktree_path.resolve()]


def test_main_repo_path_itself_is_never_in_the_exclude_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert repo_path.resolve() not in result
