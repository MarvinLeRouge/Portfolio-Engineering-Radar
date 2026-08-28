from radar_audit.runners.example import ExampleGitLogRunner

from tests.git_helpers import init_git_repo


def test_example_runner_reports_head_commit_sha(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    runner = ExampleGitLogRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert len(result.raw_output["stdout"]) == 40  # full SHA-1
    assert result.raw_output["stderr"] == ""
    assert result.duration_ms >= 0


def test_example_runner_reports_tool_identity():
    runner = ExampleGitLogRunner()

    assert runner.tool_name == "example-git-log"
    assert runner.tool_version == "1.0.0"


def test_example_runner_nonzero_exit_on_non_git_directory(tmp_path):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()

    runner = ExampleGitLogRunner()
    result = runner.run(not_a_repo, exclude_paths=[])

    assert result.exit_code != 0


def test_example_runner_declares_protocol_metadata():
    runner = ExampleGitLogRunner()

    assert runner.supported_stacks == frozenset({"unknown", "python", "javascript", "php"})
    assert runner.scope == "subproject"
    assert runner.timeout_s == 10
