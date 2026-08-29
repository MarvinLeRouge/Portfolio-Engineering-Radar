import json

import pytest
from radar_audit.runners.typescript_runner import TypeScriptRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, devDependencies=None):
    (repo_path / "package.json").write_text(
        json.dumps(
            {"name": "fixture", "version": "1.0.0", "devDependencies": devDependencies or {}}
        )
    )
    (repo_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True, "noEmit": True}})
    )


@pytest.mark.slow
def test_reports_no_diagnostics_on_well_typed_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\n"
        },
    )
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["diagnostics"] == []


@pytest.mark.slow
def test_reports_a_type_error(tmp_path):
    repo_path = tmp_path / "repo"
    code_with_error = (
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n"
        "add('x', 1);\n"
    )
    init_git_repo(repo_path, files={"src/a.ts": code_with_error})
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert len(result.raw_output["diagnostics"]) >= 1


def test_uses_typescript_package_when_vue_tsc_not_a_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary({"devDependencies": {}}) == ("typescript", "tsc")


def test_uses_vue_tsc_package_when_declared_as_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary({"devDependencies": {"vue-tsc": "^2.0.0"}}) == (
        "vue-tsc",
        "vue-tsc",
    )


def test_reports_tool_identity():
    runner = TypeScriptRunner()

    assert runner.tool_name == "tsc"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
