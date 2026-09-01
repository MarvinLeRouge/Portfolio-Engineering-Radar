from radar_audit.normalizers.code_duplication import normalize_code_duplication
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture-code-duplication")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Code quality", "Code duplication"
    )
    return audit, scoring_run, criterion


def _jscpd_result(audit_id, percentage, duplicates):
    return ToolResult(
        audit_id=audit_id,
        tool_name="jscpd",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={"statistics": {"total": {"percentage": percentage}}, "duplicates": duplicates},
        exit_code=0,
        duration_ms=10,
    )


def test_scores_ten_when_duplication_is_low(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _jscpd_result(audit.id, 1.2, [])
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_code_duplication(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_low_and_adds_findings_when_duplication_is_high(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _jscpd_result(
        audit.id,
        15.0,
        [
            {
                "firstFile": {"name": "a.js", "start": 1, "end": 20},
                "secondFile": {"name": "b.js", "start": 1, "end": 20},
            }
        ],
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_code_duplication(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_code_duplication(db_session, scoring_run, criterion, [])

    assert score is None
