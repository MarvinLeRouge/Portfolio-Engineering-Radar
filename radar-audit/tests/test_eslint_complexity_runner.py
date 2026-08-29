import json

import pytest
from radar_audit.runners.eslint_complexity_runner import EslintComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_FUNCTION = "export function add(a, b) {\n  return a + b;\n}\n"

_COMPLEX_FUNCTION = (
    "export function classify(n) {\n"
    + "".join(f"  if (n === {i}) return {i};\n" for i in range(15))
    + "  return -1;\n}\n"
)


def _write_package_json(repo_path):
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))


@pytest.mark.slow
def test_reports_low_complexity_on_a_simple_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _SIMPLE_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) <= 2


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _COMPLEX_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) >= 11


def test_reports_tool_identity():
    runner = EslintComplexityRunner()

    assert runner.tool_name == "eslint-complexity"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "src/excluded/b.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "src" / "excluded"])

    # Verify that the excluded file's violations are not in the output
    excluded_files = [c["file"] for c in result.raw_output["complexities"]]
    assert not any("excluded" in f for f in excluded_files)
