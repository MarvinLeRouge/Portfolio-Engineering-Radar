import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlmodel import Session

from radar_core.db import get_engine

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = ALEMBIC_INI.parent / "alembic"


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        del os.environ["RADAR_DATABASE_URL"]


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    assert str(engine.url).startswith(f"sqlite:///{tmp_path}")
    assert Path(engine.url.database).name != "radar.db"

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
