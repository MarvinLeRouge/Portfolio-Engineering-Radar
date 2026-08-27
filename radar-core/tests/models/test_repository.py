from datetime import UTC

from radar_core.models.repository import Repository


def test_create_repository(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    assert repo.id is not None
    assert repo.created_at.tzinfo is not None
    assert repo.created_at.tzinfo == UTC


def test_repository_path_must_be_unique(db_session):
    db_session.add(Repository(name="A", path="/same/path"))
    db_session.commit()

    db_session.add(Repository(name="B", path="/same/path"))
    with __import__("pytest").raises(Exception):
        db_session.commit()
