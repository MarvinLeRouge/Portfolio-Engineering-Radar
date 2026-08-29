from radar_audit.runners.ruff_runner import RuffRunner

from tests.git_helpers import init_git_repo


def test_reports_no_violations_on_clean_python(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a, b):\n    return a + b\n"})

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["violations"] == []
    assert result.raw_output["total_files"] == 1


def test_reports_violations_on_unused_import(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "import os\n\ndef add(a, b):\n    return a + b\n"})

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 1
    violations = result.raw_output["violations"]
    # Ruff's real default rule set also flags I001 (unsorted imports) on this
    # fixture alongside F401 — assert F401 is present rather than requiring
    # it to be the only violation.
    f401_violations = [v for v in violations if v["code"] == "F401"]
    assert len(f401_violations) == 1
    assert f401_violations[0]["filename"].endswith("a.py")
    assert result.raw_output["total_files"] == 1


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": "def add(a, b):\n    return a + b\n",
            "src/vendor/b.py": "import os\n",
        },
    )

    runner = RuffRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "vendor"])

    assert result.raw_output["violations"] == []
    assert result.raw_output["total_files"] == 1


def test_reports_tool_identity():
    runner = RuffRunner()

    assert runner.tool_name == "ruff-check"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
