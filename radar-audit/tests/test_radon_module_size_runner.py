from radar_audit.runners.radon_module_size_runner import RadonModuleSizeRunner

from tests.git_helpers import init_git_repo


def test_reports_sloc_per_python_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pkg/__init__.py": "",
            "pkg/mod.py": "x = 1\ny = 2\n\n# comment\n",
        },
    )

    runner = RadonModuleSizeRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    mod_key = str(repo_path / "pkg" / "mod.py")
    assert mod_key in result.raw_output
    assert result.raw_output[mod_key]["sloc"] == 2


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pkg/mod.py": "x = 1\n",
            "vendored/dep.py": "y = 2\n",
        },
    )

    runner = RadonModuleSizeRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "vendored"])

    assert str(repo_path / "pkg" / "mod.py") in result.raw_output
    assert str(repo_path / "vendored" / "dep.py") not in result.raw_output


def test_reports_tool_identity():
    runner = RadonModuleSizeRunner()

    assert runner.tool_name == "radon-raw"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
