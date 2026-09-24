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


def test_uses_target_path_as_cwd_not_the_caller_process_cwd(tmp_path, monkeypatch):
    # Simulates the real-world bug: radar-audit is typically invoked from a
    # directory whose own pyproject.toml declares [tool.mypy] strict = true
    # (radar-audit's own monorepo root does exactly this). Mypy resolves its
    # config from the *process's* cwd, not from any path passed on the
    # command line, so an untyped function in the analyzed target leaks in
    # as a false failure unless MypyRunner pins cwd to target_path.
    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()
    (caller_cwd / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")

    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a, b):\n    return a + b\n"})

    monkeypatch.chdir(caller_cwd)

    runner = MypyRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    # Under strict mode leaked from the wrong cwd, this untyped def would be
    # flagged as no-untyped-def. With cwd correctly pinned to target_path
    # (which has no mypy config of its own), mypy runs in default mode and
    # the file is clean.
    assert result.raw_output["diagnostics"] == []
