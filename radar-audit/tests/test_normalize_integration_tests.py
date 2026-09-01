from radar_audit.normalizers.integration_tests import normalize_integration_tests
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
        db_session, methodology_version.id, "Testing & reliability", "Integration tests"
    )
    return audit, scoring_run, criterion


def _tool_result(audit_id, total, integration):
    return ToolResult(
        audit_id=audit_id,
        tool_name="integration-test-heuristic",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={
            "total_test_files": total,
            "integration_test_files": integration,
            "files": [],
        },
        exit_code=0,
        duration_ms=10,
    )


def test_scores_ten_when_ratio_above_50_percent(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=10, integration=6)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_zero_when_no_integration_tests_present(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=5, integration=0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0


def test_returns_none_when_no_test_files_at_all(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit.id, total=0, integration=0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_integration_tests(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_integration_tests(db_session, scoring_run, criterion, [])

    assert score is None
