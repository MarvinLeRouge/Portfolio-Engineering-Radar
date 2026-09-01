from radar_audit.normalizers.ci_test_execution import normalize_ci_test_execution
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
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
        db_session, methodology_version.id, "Testing & reliability", "CI executes the test suite"
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_test_execution_found(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 1,
            "test_execution_found": True,
            "playwright_execution_found": False,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_zero_and_adds_finding_when_no_ci_runs_tests(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 0,
            "test_execution_found": False,
            "playwright_execution_found": False,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_ci_test_execution(db_session, scoring_run, criterion, [])

    assert score is None
