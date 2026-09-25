from radar_audit.runners.vulture_runner import VultureRunner

from tests.git_helpers import init_git_repo

_CLEAN_MODULE = "def add(a, b):\n    return a + b\n\nadd(1, 2)\n"

_DEAD_CODE_MODULE = (
    "def add(a, b):\n" "    return a + b\n" "\n" "def unused_helper():\n" "    return 42\n"
)

_CLI_ENTRYPOINT_MODULE = (
    "import typer\n"
    "\n"
    "app = typer.Typer()\n"
    "\n"
    "\n"
    "@app.command()\n"
    "def main():\n"
    "    print('hi')\n"
)


def test_reports_no_findings_on_clean_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _CLEAN_MODULE})

    runner = VultureRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.raw_output["findings"] == []


def test_reports_a_finding_for_an_unused_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _DEAD_CODE_MODULE})

    runner = VultureRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    findings = result.raw_output["findings"]
    assert any(f["name"] == "unused_helper" for f in findings)


def test_ignores_typer_command_decorated_entrypoints(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _CLI_ENTRYPOINT_MODULE})

    runner = VultureRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    findings = result.raw_output["findings"]
    assert not any(f["name"] == "main" for f in findings)


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _CLEAN_MODULE,
            "src/excluded/b.py": _DEAD_CODE_MODULE,
        },
    )

    runner = VultureRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    findings = result.raw_output["findings"]
    assert not any("excluded" in f["file"] for f in findings)


def test_reports_tool_identity():
    runner = VultureRunner()

    assert runner.tool_name == "vulture"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
