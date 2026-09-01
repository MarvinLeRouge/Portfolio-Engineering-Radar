from radar_audit.runners.integration_test_runner import IntegrationTestRunner

from tests.git_helpers import init_git_repo


def test_classifies_python_by_directory_name(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_unit.py": "def test_unit():\n    assert True\n",
            "tests/integration/test_flow.py": "def test_flow():\n    assert True\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_python_by_pytest_marker(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/test_unit.py": "def test_unit():\n    assert True\n",
            "tests/test_flow.py": (
                "import pytest\n\n\n"
                "@pytest.mark.integration\n"
                "def test_flow():\n    assert True\n"
            ),
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_javascript_by_integration_naming(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.test.js": "test('adds', () => {});\n",
            "src/flow.integration.test.js": "test('flow', () => {});\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_classifies_php_feature_vs_unit_by_pest_convention(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "tests/Unit/CalculatorTest.php": "<?php\n",
            "tests/Feature/FlowTest.php": "<?php\n",
        },
    )

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 2
    assert result.raw_output["integration_test_files"] == 1


def test_reports_zero_when_no_test_files_exist(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.py": "def add(a, b):\n    return a + b\n"})

    runner = IntegrationTestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["total_test_files"] == 0
    assert result.raw_output["integration_test_files"] == 0


def test_reports_tool_identity():
    runner = IntegrationTestRunner()

    assert runner.tool_name == "integration-test-heuristic"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset({"python", "javascript", "php"})
