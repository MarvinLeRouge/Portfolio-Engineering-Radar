from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
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
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Architectural documentation present",
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="design-doc-presence",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_absent_scores_zero_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"found_path": None, "non_blank_lines": 0})

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 0.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].severity == "LOW"


def test_present_and_trivial_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"found_path": "/repo/DESIGN.md", "non_blank_lines": 5}
    )

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_present_and_non_trivial_scores_ten_with_no_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"found_path": "/repo/DESIGN.md", "non_blank_lines": 40}
    )

    score = normalize_design_doc(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_returns_none_when_no_relevant_tool_results(db_session):
    _, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_design_doc(db_session, scoring_run, criterion, [])

    assert score is None
