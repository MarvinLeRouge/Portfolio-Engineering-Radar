from radar_audit.cli import app
from typer.testing import CliRunner

from tests.conftest import RADAR_CORE_ROOT
from tests.git_helpers import init_git_repo

runner = CliRunner()


def _migrate(db_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")
    alembic_config = Config(str(RADAR_CORE_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(RADAR_CORE_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")


def _write_config(tmp_path, repos_root, repo_names):
    path = tmp_path / "portfolio.yaml"
    repos_yaml = "\n".join(f"  - name: {name}" for name in repo_names)
    path.write_text(f"repos_root: {repos_root}\nrepositories:\n{repos_yaml}\n")
    return path


def test_score_command_fails_cleanly_for_unknown_repo(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    result = runner.invoke(app, ["score", "not-a-real-repo"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "Error:" in result.stderr
    assert "not-a-real-repo" in result.stderr


def test_score_command_persists_scores_for_an_audited_repo(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path, files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"})
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    run_result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])
    assert run_result.exit_code == 0

    score_result = runner.invoke(app, ["score", "sample-repo"])
    assert score_result.exit_code == 0

    from radar_core.db import get_engine
    from radar_core.enums import ScoreLevel
    from radar_core.models.scoring import Score
    from sqlmodel import Session, select

    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        scores = session.exec(select(Score)).all()
        assert any(s.level == ScoreLevel.CRITERION for s in scores)


def test_report_command_fails_cleanly_when_not_scored_yet(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    run_result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])
    assert run_result.exit_code == 0

    report_result = runner.invoke(app, ["report", "sample-repo"])

    assert report_result.exit_code == 1
    assert "Error:" in report_result.stderr
    assert "sample-repo" in report_result.stderr


def test_report_command_writes_markdown_to_output_dir(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(
        repo_path,
        files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"},
    )
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    _migrate(db_path, monkeypatch)

    assert runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)]).exit_code == 0
    assert runner.invoke(app, ["score", "sample-repo"]).exit_code == 0

    output_dir = tmp_path / "reports"
    report_result = runner.invoke(app, ["report", "sample-repo", "--output-dir", str(output_dir)])

    assert report_result.exit_code == 0
    written = output_dir / "sample-repo" / "latest.md"
    assert written.exists()
    assert "# Report: sample-repo" in written.read_text()
