# tests/test_eslint_lint_runner.py
import json

import pytest
from radar_audit.runners.eslint_lint_runner import EslintLintRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, lint_script):
    (repo_path / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "1.0.0", "scripts": {"lint": lint_script}})
    )
    (repo_path / "eslint.config.js").write_text(
        'module.exports = [{ rules: { "no-unused-vars": "error" } }];\n'
    )


@pytest.mark.slow
def test_reports_no_violations_on_clean_js(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert all(entry["errorCount"] == 0 for entry in result.raw_output["results"])


@pytest.mark.slow
def test_reports_violations_on_unused_variable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export function add(a, b) {\n  const unused = 1;\n  return a + b;\n}\n"
        },
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    flagged = [e for e in result.raw_output["results"] if e["errorCount"] > 0]
    assert len(flagged) == 1


@pytest.mark.slow
def test_falls_back_to_target_path_when_no_lint_script(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))
    (repo_path / "eslint.config.js").write_text("module.exports = [{}];\n")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["results"]


def test_reports_tool_identity():
    runner = EslintLintRunner()

    assert runner.tool_name == "eslint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
