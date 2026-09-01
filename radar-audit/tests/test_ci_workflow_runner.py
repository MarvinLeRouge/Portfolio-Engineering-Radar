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

_LARAVEL_ARTISAN_TEST_WORKFLOW = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: php artisan test --coverage --min=80
"""

_NPM_SCRIPT_WORKFLOW = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run coverage
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run test:e2e
"""

_NPM_SCRIPT_PACKAGE_JSON = """{
  "scripts": {
    "coverage": "vitest run --coverage",
    "test:e2e": "playwright test"
  }
}
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


def test_detects_php_artisan_test_as_test_execution(tmp_path):
    # Real-world shape found auditing Summit-Stats: Laravel's own `php artisan
    # test` wrapper, not the raw `pest`/`phpunit` binary name.
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _LARAVEL_ARTISAN_TEST_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is True


def test_resolves_npm_run_script_indirection_against_package_json(tmp_path):
    # Real-world shape found auditing Summit-Stats: CI invokes `npm run
    # coverage` / `npm run test:e2e`, hiding the actual vitest/Playwright
    # command behind a package.json script name that carries no literal
    # test/Playwright keyword of its own.
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            ".github/workflows/ci.yml": _NPM_SCRIPT_WORKFLOW,
            "package.json": _NPM_SCRIPT_PACKAGE_JSON,
        },
    )

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is True
    assert result.raw_output["playwright_execution_found"] is True


def test_npm_run_script_indirection_is_a_noop_without_package_json(tmp_path):
    # Without package.json to resolve against, `npm run coverage` carries no
    # test/Playwright keyword of its own -- unlike `npm run test:e2e`, whose
    # script name still contains the literal "test" substring.
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _NPM_SCRIPT_WORKFLOW})

    runner = CiWorkflowRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["test_execution_found"] is True
    assert result.raw_output["playwright_execution_found"] is False


def test_reports_tool_identity():
    runner = CiWorkflowRunner()

    assert runner.tool_name == "ci-workflow"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
