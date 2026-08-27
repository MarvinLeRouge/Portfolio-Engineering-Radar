from radar_core.db import get_engine, get_session


def test_get_engine_binds_to_given_url(tmp_path):
    db_path = tmp_path / "engine_test.db"
    engine = get_engine(f"sqlite:///{db_path}")

    assert str(engine.url) == f"sqlite:///{db_path}"


def test_two_engines_on_different_urls_are_independent(tmp_path):
    engine_a = get_engine(f"sqlite:///{tmp_path / 'a.db'}")
    engine_b = get_engine(f"sqlite:///{tmp_path / 'b.db'}")

    assert engine_a.url != engine_b.url


def test_get_session_returns_open_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'session_test.db'}")

    session = get_session(engine)
    try:
        assert session.is_active
    finally:
        session.close()
