import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from radar_core.db import get_engine
from sqlmodel import Session

RADAR_CORE_ROOT = Path(__file__).resolve().parents[2] / "radar-core"
ALEMBIC_INI = RADAR_CORE_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = RADAR_CORE_ROOT / "alembic"


def _run_migrations(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    previous_url = os.environ.get("RADAR_DATABASE_URL")
    os.environ["RADAR_DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_url is None:
            del os.environ["RADAR_DATABASE_URL"]
        else:
            os.environ["RADAR_DATABASE_URL"] = previous_url


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    _run_migrations(database_url)

    engine = get_engine(database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
