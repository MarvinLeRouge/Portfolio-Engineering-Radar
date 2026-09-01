from radar_audit.runners.pytest_coverage_runner import PytestCoverageRunner

from tests.git_helpers import init_git_repo


def test_reports_full_pass_and_coverage(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_add.py": (
                "def add(a, b):\n"
                "    return a + b\n\n\n"
                "def test_add():\n"
                "    assert add(1, 2) == 3\n"
            ),
        },
    )

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 1
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


def test_reports_failures_with_best_effort_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_add.py": (
                "def add(a, b):\n"
                "    return a + b\n\n\n"
                "def test_add():\n"
                "    assert add(1, 2) == 4\n"
            ),
        },
    )

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "tests/test_add.py"


def test_reports_zero_collected_as_no_tests(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"tests/helper.py": "def not_a_test():\n    pass\n"})

    runner = PytestCoverageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 5
    assert result.raw_output["tests"]["total"] == 0
    assert result.raw_output["coverage_percent"] is None


def test_reports_tool_identity():
    runner = PytestCoverageRunner()

    assert runner.tool_name == "pytest-cov"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
