from radar_audit.normalizers.sast_findings import normalize_sast_findings
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
    criterion = get_criterion(db_session, methodology_version.id, "Security", "SAST findings")
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="semgrep",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_results_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"results": []})

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_error_severity_scores_four_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.subprocess-shell-true",
                    "path": "src/vuln.py",
                    "start": {"line": 4},
                    "extra": {"severity": "ERROR", "message": "shell=True is dangerous"},
                }
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "src/vuln.py"
    assert findings[0].line == 4


def test_warning_severity_scores_six(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "x.warning-rule",
                    "path": "a.py",
                    "start": {"line": 1},
                    "extra": {"severity": "WARNING", "message": "m"},
                }
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_worst_severity_wins_across_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "x.info-rule",
                    "path": "a.py",
                    "start": {"line": 1},
                    "extra": {"severity": "INFO", "message": "m"},
                },
                {
                    "check_id": "x.error-rule",
                    "path": "b.py",
                    "start": {"line": 1},
                    "extra": {"severity": "ERROR", "message": "m"},
                },
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    unrelated = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="ruff-check",
        tool_version="1.0.0",
        command="stub",
        raw_output={"violations": []},
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(unrelated)
    db_session.commit()
    db_session.refresh(unrelated)

    score = normalize_sast_findings(db_session, scoring_run, criterion, [unrelated])

    assert score is None


def test_orchestrator_crash_record_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [crashed])

    assert score is None


def test_failed_scan_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    failed = _make_tool_result(
        db_session,
        audit,
        {
            "error": "semgrep scan failed",
            "errors": [{"code": 2, "level": "error", "message": "HTTP 404"}],
            "stdout": "",
            "stderr": "",
        },
        exit_code=7,
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [failed])

    assert score is None


def test_crash_record_is_excluded_when_a_successful_scan_exists(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )
    succeeded = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.eval",
                    "path": "src/a.py",
                    "start": {"line": 1},
                    "extra": {"severity": "WARNING", "message": "eval detected"},
                }
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [crashed, succeeded])

    assert score.value == 6.0
