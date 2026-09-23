import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.orchestrator import execute_audit
from radar_audit.report import NoScoringRunFoundError, render_report, write_report
from radar_audit.scoring import RepositoryNotFoundError, score_repository

from tests.git_helpers import init_git_repo


def _scored_repo(db_session, tmp_path, name="repo"):
    repo_path = tmp_path / name
    init_git_repo(
        repo_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    execute_audit(db_session, config, name, DEFAULT_RUNNERS)
    return score_repository(db_session, name)


def test_render_report_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError):
        render_report(db_session, "does-not-exist")


def test_render_report_raises_when_no_score_exists(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    with pytest.raises(NoScoringRunFoundError):
        render_report(db_session, "repo")


def test_render_report_shows_scored_categories_and_not_yet_audited_placeholders(
    db_session, tmp_path
):
    _scored_repo(db_session, tmp_path)

    markdown = render_report(db_session, "repo")

    assert "# Report: repo" in markdown
    assert "Architecture & design" in markdown
    assert "Not yet audited" in markdown  # category 4 (Security) has no data yet
    assert "not scored this run" in markdown  # 1.4 has no normalizer


def test_write_report_creates_file_under_repo_named_subdir(db_session, tmp_path):
    _scored_repo(db_session, tmp_path)
    markdown = render_report(db_session, "repo")

    output_dir = tmp_path / "reports"
    written_path = write_report(markdown, "repo", output_dir)

    assert written_path == output_dir / "repo" / "latest.md"
    assert written_path.read_text() == markdown
