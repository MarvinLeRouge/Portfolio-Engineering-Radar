from radar_audit.runners.design_doc_runner import DesignDocRunner

from tests.git_helpers import init_git_repo


def test_reports_absent_when_no_doc_or_adr_dir_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["found_path"] is None
    assert result.raw_output["non_blank_lines"] == 0


def test_finds_design_md_at_repo_root(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"})

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "DESIGN.md")
    assert result.raw_output["non_blank_lines"] == 40


def test_finds_architecture_md_in_docs_directory(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"docs/ARCHITECTURE.md": "line one\nline two\n"})

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "docs" / "ARCHITECTURE.md")
    assert result.raw_output["non_blank_lines"] == 2


def test_sums_lines_across_adr_directory_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "docs/adr/0001-use-sqlite.md": "line one\nline two\n",
            "docs/adr/0002-use-typer.md": "line one\n",
        },
    )

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "docs" / "adr")
    assert result.raw_output["non_blank_lines"] == 3


def test_root_design_md_takes_priority_over_adr_directory(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "DESIGN.md": "line one\n",
            "docs/adr/0001-use-sqlite.md": "line one\nline two\nline three\n",
        },
    )

    runner = DesignDocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["found_path"] == str(repo_path / "DESIGN.md")
    assert result.raw_output["non_blank_lines"] == 1


def test_reports_tool_identity():
    runner = DesignDocRunner()

    assert runner.tool_name == "design-doc-presence"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
