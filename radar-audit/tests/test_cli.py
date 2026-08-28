from radar_audit.cli import app
from sqlmodel import Session, select
from typer.testing import CliRunner

from tests.conftest import RADAR_CORE_ROOT
from tests.git_helpers import init_git_repo

runner = CliRunner()


def _write_config(tmp_path, repos_root, repo_names):
    path = tmp_path / "portfolio.yaml"
    repos_yaml = "\n".join(f"  - name: {name}" for name in repo_names)
    path.write_text(f"repos_root: {repos_root}\nrepositories:\n{repos_yaml}\n")
    return path


def test_dry_run_prints_plan_and_writes_nothing_to_disk(tmp_path):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "sample-repo" in result.stdout
    assert "example-git-log" in result.stdout
    assert not (tmp_path / "radar.db").exists()


def test_run_without_repo_name_or_all_fails(tmp_path):
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    result = runner.invoke(app, ["run", "--config", str(config_path)])

    assert result.exit_code != 0


def test_real_run_persists_audit_and_tool_results(tmp_path, monkeypatch):
    repo_path = tmp_path / "repos" / "sample-repo"
    init_git_repo(repo_path)
    config_path = _write_config(tmp_path, tmp_path / "repos", ["sample-repo"])

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{db_path}")

    from alembic import command
    from alembic.config import Config

    alembic_config = Config(str(RADAR_CORE_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(RADAR_CORE_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")

    result = runner.invoke(app, ["run", "sample-repo", "--config", str(config_path)])

    assert result.exit_code == 0
    assert db_path.exists()

    from radar_core.db import get_engine
    from radar_core.models.audit import Audit, ToolResult

    engine = get_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        audits = session.exec(select(Audit)).all()
        assert len(audits) == 1
        results = session.exec(select(ToolResult)).all()
        assert len(results) == 1
        assert results[0].tool_name == "example-git-log"
