from radar_audit.runners.ci_workflow_runner import CiWorkflowRunner

from tests.git_helpers import init_git_repo

_TEST_WORKFLOW = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest
"""

_PLAYWRIGHT_WORKFLOW = """name: E2E
on: [push]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx playwright test
"""

_UNRELATED_WORKFLOW = """name: Lint
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx eslint .
"""


def test_detects_test_execution(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _TEST_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["workflows_found"] == 1
    assert result.raw_output["test_execution_found"] is True
    assert result.raw_output["playwright_execution_found"] is False


def test_detects_playwright_execution(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/e2e.yml": _PLAYWRIGHT_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is False
    assert result.raw_output["playwright_execution_found"] is True


def test_reports_both_false_for_unrelated_workflow(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/lint.yml": _UNRELATED_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is False
    assert result.raw_output["playwright_execution_found"] is False


def test_reports_zero_workflows_when_directory_absent(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "# fixture\n"})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["workflows_found"] == 0
    assert result.raw_output["test_execution_found"] is False


def test_reports_tool_identity():
    runner = CiWorkflowRunner()

    assert runner.tool_name == "ci-workflow"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
