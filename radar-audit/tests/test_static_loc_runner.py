from radar_audit.runners.static_loc_runner import StaticLocRunner

from tests.git_helpers import init_git_repo


def test_counts_non_blank_lines_per_source_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "line one\n\nline three\n",
            "src/b.php": "<?php\necho 1;\n",
            "README.md": "not counted\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    files = result.raw_output["files"]
    assert files[str(repo_path / "src" / "a.js")] == 2
    assert files[str(repo_path / "src" / "b.php")] == 2
    assert str(repo_path / "README.md") not in files
    assert result.exit_code == 0


def test_skips_vendor_and_node_modules_directories(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "line\n",
            "node_modules/pkg/index.js": "line\n",
            "vendor/lib/file.php": "<?php\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    files = result.raw_output["files"]
    assert set(files) == {str(repo_path / "src" / "a.js")}


def test_reports_tool_identity():
    runner = StaticLocRunner()

    assert runner.tool_name == "static-loc-count"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript", "php"})


def test_counts_files_even_when_repo_path_contains_skip_dirname(tmp_path):
    """Regression test: repo checked out under a dir named 'vendor' or 'dist' etc.
    should still count source files at the repo root, since the skip list applies
    to relative paths within the scanned project, not the absolute checkout path.
    """
    repo_root = tmp_path / "vendor" / "repo"
    init_git_repo(
        repo_root,
        files={
            "src/a.js": "line one\n",
            "main.php": "<?php\necho 1;\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_root, exclude_paths=[])

    files = result.raw_output["files"]
    assert str(repo_root / "src" / "a.js") in files
    assert files[str(repo_root / "src" / "a.js")] == 1
    assert str(repo_root / "main.php") in files
    assert files[str(repo_root / "main.php")] == 2
