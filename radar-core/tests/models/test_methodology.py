from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion


def test_create_methodology_with_category_and_criterion(db_session):
    version = MethodologyVersion(version_label="1.0", notes="Frozen 2026-08-26")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(
        methodology_version_id=version.id, name="Security", weight=1.5, order=4
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks, git-history mode",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    assert criterion.id is not None
    assert criterion.category_id == category.id
    assert category.methodology_version_id == version.id


def test_methodology_version_label_must_be_unique(db_session):
    db_session.add(MethodologyVersion(version_label="1.0"))
    db_session.commit()

    db_session.add(MethodologyVersion(version_label="1.0"))
    with __import__("pytest").raises(Exception):
        db_session.commit()
