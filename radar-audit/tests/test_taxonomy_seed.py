from pathlib import Path

from radar_audit.taxonomy.seed import TAXONOMY_PATH, seed_taxonomy
from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from sqlmodel import select

SAMPLE_YAML = Path(__file__).parent / "fixtures" / "taxonomy_sample.yaml"


def test_seed_taxonomy_creates_version_categories_and_criteria(db_session):
    seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)

    version = db_session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == "Sample Taxonomy v0.1")
    ).first()
    assert version is not None

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == version.id)
    ).all()
    assert len(categories) == 2

    criteria = db_session.exec(
        select(Criterion).where(Criterion.category_id.in_([c.id for c in categories]))
    ).all()
    assert len(criteria) == 3
    assert {c.scoring_model for c in criteria} == {
        ScoringModel.FIXED_SCALE,
        ScoringModel.STATUS_4STATE,
    }


def test_seed_taxonomy_is_idempotent(db_session):
    first = seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)
    second = seed_taxonomy(db_session, yaml_path=SAMPLE_YAML)

    assert first.id == second.id

    versions = db_session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == "Sample Taxonomy v0.1")
    ).all()
    assert len(versions) == 1

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == first.id)
    ).all()
    assert len(categories) == 2


def test_seed_taxonomy_default_path_loads_the_real_catalog(db_session):
    version = seed_taxonomy(db_session)

    assert version.version_label == "Quality Framework v1.0"

    categories = db_session.exec(
        select(Category).where(Category.methodology_version_id == version.id)
    ).all()
    assert len(categories) == 15

    criteria = db_session.exec(
        select(Criterion).where(Criterion.category_id.in_([c.id for c in categories]))
    ).all()
    assert len(criteria) == 51

    for category in categories:
        category_criteria = [c for c in criteria if c.category_id == category.id]
        assert len(category_criteria) > 0

    total_category_weight = sum(c.weight for c in categories)
    assert abs(total_category_weight - 100.0) < 0.2

    assert TAXONOMY_PATH.exists()
