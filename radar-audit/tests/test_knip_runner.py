import json

import pytest
from radar_audit.runners.knip_runner import KnipRunner

from tests.git_helpers import init_git_repo

_USED_HELPER = "export function used() {\n  return 1;\n}\n"

_HELPER_WITH_UNUSED_EXPORT = (
    "export function used() {\n  return 1;\n}\n\nexport function unusedExport() {\n  return 2;\n}\n"
)

_MAIN_JS = 'import { used } from "./helpers.js";\nconsole.log(used());\n'

_INDEX_HTML = (
    "<!doctype html>\n<html><body>"
    '<script type="module" src="/src/main.js"></script>'
    "</body></html>\n"
)


def _write_package_json(repo_path):
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "type": "module"}))


@pytest.mark.slow
def test_reports_no_issues_when_all_exports_are_used(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["issues"] == []


@pytest.mark.slow
def test_reports_an_unused_export(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    issues = result.raw_output["issues"]
    exported_names = {e["name"] for issue in issues for e in issue.get("exports", [])}
    assert "unusedExport" in exported_names


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
            "excluded/nested/orphan.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "excluded"])

    issues = result.raw_output["issues"]
    reported_files = {issue["file"] for issue in issues}
    reported_files |= {f["name"] for issue in issues for f in issue.get("files", [])}
    assert not any(name.startswith("excluded") for name in reported_files)


@pytest.mark.slow
def test_reports_the_orphan_file_when_it_is_not_excluded(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
            "excluded/nested/orphan.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    issues = result.raw_output["issues"]
    reported_files = {f["name"] for issue in issues for f in issue.get("files", [])}
    assert "excluded/nested/orphan.js" in reported_files


def test_returns_an_unusable_payload_when_no_entry_point_candidate_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/helpers.js": _USED_HELPER})
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert "issues" not in result.raw_output
    assert result.raw_output == {"stdout": "", "stderr": "no entry point candidate found"}


def test_reports_tool_identity():
    runner = KnipRunner()

    assert runner.tool_name == "knip"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
