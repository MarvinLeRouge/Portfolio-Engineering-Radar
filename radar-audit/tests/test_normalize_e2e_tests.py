from radar_audit.normalizers.e2e_tests import normalize_e2e_tests
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.repository import Repository


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
        db_session, methodology_version.id, "Testing & reliability", "E2E tests"
    )
    return audit, scoring_run, criterion


def _playwright_result(audit_id, present, subproject_path="frontend"):
    return ToolResult(
        audit_id=audit_id,
        tool_name="playwright-presence",
        tool_version="1.0.0",
        subproject_path=subproject_path,
        command="stub",
        raw_output={"present": present},
        exit_code=0,
        duration_ms=10,
    )


def _ci_result(audit_id, playwright_execution_found):
    return ToolResult(
        audit_id=audit_id,
        tool_name="ci-workflow",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "workflows_found": 1,
            "test_execution_found": True,
            "playwright_execution_found": playwright_execution_found,
        },
        exit_code=0,
        duration_ms=10,
    )


def test_scores_done_when_present_and_wired_into_ci(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=True)
    ci_result = _ci_result(audit.id, playwright_execution_found=True)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(db_session, scoring_run, criterion, [playwright_result, ci_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_in_progress_when_present_but_not_wired(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=True)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(db_session, scoring_run, criterion, [playwright_result, ci_result])

    assert score is not None
    assert score.value == 5.0


def test_scores_todo_when_absent(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    playwright_result = _playwright_result(audit.id, present=False)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(playwright_result)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(db_session, scoring_run, criterion, [playwright_result, ci_result])

    assert score is not None
    assert score.value == 0.0


def test_returns_none_when_no_javascript_subproject(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    ci_result = _ci_result(audit.id, playwright_execution_found=False)
    db_session.add(ci_result)
    db_session.commit()

    score = normalize_e2e_tests(db_session, scoring_run, criterion, [ci_result])

    assert score is None
