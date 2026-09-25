from radar_audit.runners.docvet_runner import DocvetRunner

from tests.git_helpers import init_git_repo

_FULLY_DOCUMENTED_MODULE = (
    '"""Module docstring."""\n'
    "\n"
    "def add(a, b):\n"
    '    """Add two numbers."""\n'
    "    return a + b\n"
)

_PARTIALLY_DOCUMENTED_MODULE = (
    "def add(a, b):\n"
    '    """Add two numbers."""\n'
    "    return a + b\n"
    "\n"
    "def subtract(a, b):\n"
    "    return a - b\n"
)


def test_reports_full_coverage_on_a_fully_documented_module(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _FULLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["presence_coverage"]["percentage"] == 100.0


def test_reports_partial_coverage_and_a_finding_on_an_undocumented_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _PARTIALLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["presence_coverage"]["percentage"] < 100.0
    assert any(f["symbol"] == "subtract" for f in result.raw_output["findings"])


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/excluded/b.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    findings = result.raw_output.get("findings", [])
    assert not any("excluded" in f["file"] for f in findings)


def test_excludes_nested_paths_more_than_one_level_deep(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/apps/web/lib/y.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "apps" / "web"])

    assert result.raw_output["presence_coverage"]["percentage"] == 100.0
    findings = result.raw_output.get("findings", [])
    assert not any("apps/web" in f["file"] for f in findings)


def test_keeps_docvet_default_exclusion_of_tests_and_scripts(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/tests/test_a.py": _PARTIALLY_DOCUMENTED_MODULE,
            "src/scripts/tool.py": _PARTIALLY_DOCUMENTED_MODULE,
            "src/excluded/b.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    assert result.raw_output["presence_coverage"]["percentage"] == 100.0
    assert result.raw_output.get("findings", []) == []


def test_falls_back_to_stdout_when_no_python_files_remain(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _FULLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src"])

    assert "presence_coverage" not in result.raw_output


def test_reports_tool_identity():
    runner = DocvetRunner()

    assert runner.tool_name == "docvet"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
