from radar_core.enums import Confidence
from radar_core.models.snapshot import Snapshot


def test_create_snapshot(db_session):
    snapshot = Snapshot(
        portfolio_global_score=7.8,
        portfolio_global_confidence=Confidence.MEDIUM,
        details={"repositories": [{"name": "GeoChallenge-Tracker", "score": 8.1}]},
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.details["repositories"][0]["name"] == "GeoChallenge-Tracker"
