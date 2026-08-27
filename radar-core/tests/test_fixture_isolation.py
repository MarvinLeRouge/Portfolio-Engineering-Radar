from pathlib import Path

from sqlalchemy import inspect


def test_fixture_creates_file_inside_tmp_path(db_session, tmp_path):
    expected_path = tmp_path / "test.db"
    assert expected_path.exists()
    assert str(db_session.get_bind().url).startswith(f"sqlite:///{tmp_path}")


def test_fixture_never_points_at_production_db(db_session):
    assert Path(db_session.get_bind().url.database).name != "radar.db"


def test_migration_ran_against_the_fixture_file(db_session):
    inspector = inspect(db_session.get_bind())
    assert "alembic_version" in inspector.get_table_names()
