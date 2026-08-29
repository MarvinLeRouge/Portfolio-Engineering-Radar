from radar_audit.runners.pydeps_runner import PydepsRunner

from tests.git_helpers import init_git_repo


def test_reports_no_cycle_on_a_clean_package(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
        },
    )

    runner = PydepsRunner()
    result = runner.run(repo_path / "mypkg", exclude_paths=[])

    assert result.exit_code == 0
    assert "mypkg.a" in result.raw_output
    assert result.raw_output["mypkg.a"]["imports"] == ["mypkg", "mypkg.b"]
    assert "imports" not in result.raw_output["mypkg.b"]


def test_reports_a_circular_import_between_two_modules(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "from mypkg import a\n",
        },
    )

    runner = PydepsRunner()
    result = runner.run(repo_path / "mypkg", exclude_paths=[])

    assert result.exit_code == 0
    assert set(result.raw_output["mypkg.a"]["imports"]) == {"mypkg", "mypkg.b"}
    assert set(result.raw_output["mypkg.b"]["imports"]) == {"mypkg", "mypkg.a"}


def test_reports_tool_identity():
    runner = PydepsRunner()

    assert runner.tool_name == "pydeps"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
