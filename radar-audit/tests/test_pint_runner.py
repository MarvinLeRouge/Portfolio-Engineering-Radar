import subprocess

import pytest
from radar_audit.runners.pint_runner import PintRunner

from tests.git_helpers import init_git_repo


def _install_local_pint(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"laravel/pint": "^1.0"}}\n'
    )
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_pass_on_correctly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A {}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["result"] == "passed"


@pytest.mark.slow
def test_reports_fail_on_badly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\nclass A{\npublic function f(){}\n}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["result"] == "fail"


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n"})

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PintRunner()

    assert runner.tool_name == "pint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
