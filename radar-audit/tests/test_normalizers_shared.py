import pytest
from radar_audit.normalizers.shared import (
    CriterionNotFoundError,
    get_criterion,
    get_or_create_scoring_run,
)
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit
from radar_core.models.repository import Repository


def _make_audit(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_get_or_create_scoring_run_creates_a_new_run(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert scoring_run.id is not None
    assert scoring_run.audit_id == audit.id
    assert scoring_run.methodology_version_id == methodology_version.id


def test_get_or_create_scoring_run_reuses_existing(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)

    first = get_or_create_scoring_run(db_session, audit, methodology_version)
    second = get_or_create_scoring_run(db_session, audit, methodology_version)

    assert first.id == second.id


def test_get_criterion_finds_a_seeded_criterion(db_session):
    methodology_version = seed_taxonomy(db_session)

    criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Dependency direction / circularity",
    )

    assert criterion.name == "Dependency direction / circularity"


def test_get_criterion_raises_when_not_found(db_session):
    methodology_version = seed_taxonomy(db_session)

    with pytest.raises(CriterionNotFoundError):
        get_criterion(db_session, methodology_version.id, "Nonexistent", "Nope")
