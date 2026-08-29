from radar_audit.runners.mypy_runner import MypyRunner

from tests.git_helpers import init_git_repo


def test_reports_no_diagnostics_on_well_typed_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.py": "def add(a: int, b: int) -> int:\n    return a + b\n"}
    )

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["diagnostics"] == []


def test_reports_a_type_error(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"src/a.py": "def add(a: int, b: int) -> int:\n    return a + b\n\nadd('x', 1)\n"},
    )

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 1
    diagnostics = result.raw_output["diagnostics"]
    assert any(d["severity"] == "error" for d in diagnostics)


def test_reports_tool_identity():
    runner = MypyRunner()

    assert runner.tool_name == "mypy"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
            "src/vendor/b.py": "def bad(x: int) -> str:\n    return x\n",
        },
    )

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "vendor"])

    assert result.raw_output["diagnostics"] == []
    assert result.raw_output["total_files"] == 1
