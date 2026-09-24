from radar_audit.runners.jscpd_runner import JscpdRunner

from tests.git_helpers import init_git_repo

_UNIQUE_A = "export function add(a, b) {\n  return a + b;\n}\n"
_UNIQUE_B = "export function multiply(a, b) {\n  return a * b;\n}\n"

_DUPLICATE_BLOCK = "\n".join(f"  const line{i} = {i};" for i in range(20))
_DUPLICATE_A = f"export function first() {{\n{_DUPLICATE_BLOCK}\n  return 1;\n}}\n"
_DUPLICATE_B = f"export function second() {{\n{_DUPLICATE_BLOCK}\n  return 2;\n}}\n"


def test_reports_a_low_percentage_on_unique_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _UNIQUE_A, "src/b.js": _UNIQUE_B})

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["statistics"]["total"]["percentage"] < 5.0


def test_reports_duplicates_across_two_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _DUPLICATE_A, "src/b.js": _DUPLICATE_B})

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
    assert result.raw_output["statistics"]["total"]["percentage"] > 0.0


def test_excludes_node_modules_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _UNIQUE_A,
            "node_modules/pkg/a.js": _DUPLICATE_A,
            "node_modules/pkg/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    duplicate_files = {d["firstFile"]["name"] for d in result.raw_output["duplicates"]} | {
        d["secondFile"]["name"] for d in result.raw_output["duplicates"]
    }
    assert all("node_modules" not in name for name in duplicate_files)


def test_excludes_docs_directory_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _DUPLICATE_A,
            "src/b.js": _DUPLICATE_B,
            "docs/superpowers/plans/a.js": _DUPLICATE_A,
            "docs/superpowers/plans/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
    duplicate_files = {d["firstFile"]["name"] for d in result.raw_output["duplicates"]} | {
        d["secondFile"]["name"] for d in result.raw_output["duplicates"]
    }
    assert all("docs" not in name for name in duplicate_files)


def test_does_not_exclude_a_directory_whose_name_merely_contains_docs(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "docsite/a.js": _DUPLICATE_A,
            "docsite/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]


def test_excludes_dot_directories_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _DUPLICATE_A,
            "src/b.js": _DUPLICATE_B,
            ".venv/lib/a.js": _DUPLICATE_A,
            ".venv/lib/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
    duplicate_files = {d["firstFile"]["name"] for d in result.raw_output["duplicates"]} | {
        d["secondFile"]["name"] for d in result.raw_output["duplicates"]
    }
    assert all(".venv" not in name for name in duplicate_files)


def test_still_detects_duplicates_when_target_repo_is_nested_under_a_dot_or_docs_ancestor(
    tmp_path,
):
    repo_path = tmp_path / ".hidden" / "docs" / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _DUPLICATE_A,
            "src/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
    assert result.raw_output["statistics"]["total"]["sources"] >= 2


def test_does_not_exclude_a_regular_directory_that_is_not_dot_prefixed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "notdot/a.js": _DUPLICATE_A,
            "notdot/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]


def test_reports_tool_identity():
    runner = JscpdRunner()

    assert runner.tool_name == "jscpd"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
