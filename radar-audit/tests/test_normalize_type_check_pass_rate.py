# tests/test_normalize_type_check_pass_rate.py
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.type_check_pass_rate import normalize_type_check_pass_rate
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _setup(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
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
        db_session, methodology_version.id, "Code quality", "Type-checking pass"
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_mypy_is_fully_clean(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="mypy",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"diagnostics": [], "total_files": 3},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_lowers_score_and_adds_findings_for_phpstan_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="phpstan",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "totals": {"errors": 1, "file_errors": 1},
            "files": {"src/A.php": {"errors": 1, "messages": [{"message": "bad type", "line": 5}]}},
            "errors": [],
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1
    assert findings[0].file == "src/A.php"


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_type_check_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None
