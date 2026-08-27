import pytest
from sqlalchemy.exc import IntegrityError

from radar_core.enums import Confidence, ScoreLevel, ScoringModel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun


def _make_audit_and_methodology(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    return audit, version, category, criterion


def test_create_scoring_run_with_scores(db_session):
    audit, version, category, criterion = _make_audit_and_methodology(db_session)

    scoring_run = ScoringRun(
        audit_id=audit.id, methodology_version_id=version.id, global_score=7.5,
        global_confidence=Confidence.HIGH,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    criterion_score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=10.0,
        confidence=Confidence.HIGH,
    )
    category_score = Score(
        scoring_run_id=scoring_run.id,
        category_id=category.id,
        level=ScoreLevel.CATEGORY,
        value=10.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(criterion_score)
    db_session.add(category_score)
    db_session.commit()

    assert scoring_run.id is not None
    assert criterion_score.criterion_id == criterion.id
    assert category_score.category_id == category.id


def test_scoring_run_unique_per_audit_and_methodology(db_session):
    audit, version, _category, _criterion = _make_audit_and_methodology(db_session)

    db_session.add(ScoringRun(audit_id=audit.id, methodology_version_id=version.id))
    db_session.commit()

    db_session.add(ScoringRun(audit_id=audit.id, methodology_version_id=version.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
