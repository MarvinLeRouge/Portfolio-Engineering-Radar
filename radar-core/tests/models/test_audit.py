import pytest
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository
from sqlalchemy.exc import IntegrityError


def _make_repository(db_session) -> Repository:
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def test_create_audit_with_tool_result(db_session):
    repo = _make_repository(db_session)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="gitleaks",
        tool_version="8.18.0",
        command="gitleaks detect --report-format json",
        raw_output={"findings": []},
        exit_code=0,
        duration_ms=420,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)

    assert tool_result.audit_id == audit.id
    assert tool_result.subproject_path == "."
    assert tool_result.raw_output == {"findings": []}


def test_second_clean_audit_on_same_commit_is_rejected(db_session):
    repo = _make_repository(db_session)

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False))
    db_session.commit()

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_dirty_audits_on_same_commit_are_allowed(db_session):
    repo = _make_repository(db_session)

    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=True))
    db_session.add(Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=True))
    db_session.commit()  # must not raise
