from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.normalizers.unit_test_pass_rate import normalize_unit_test_pass_rate
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
        db_session,
        methodology_version.id,
        "Testing & reliability",
        "Unit tests present & passing, with coverage",
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_all_tests_pass(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 3, "passed": 3, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": 90.0,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_sums_ratio_across_subprojects_and_adds_finding_for_failures(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 2, "passed": 1, "failed": 1, "skipped": 0},
            "failures": [{"file": "tests/test_a.py", "name": "test_a", "line": None}],
            "coverage_percent": 40.0,
        },
        exit_code=1,
        duration_ms=10,
    )
    frontend = ToolResult(
        audit_id=audit.id,
        tool_name="vitest",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={
            "tests": {"total": 2, "passed": 2, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": 95.0,
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(backend)
    db_session.add(frontend)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [backend, frontend])

    assert score is not None
    assert score.value == 7.5  # (1 + 2) / (2 + 2) * 10

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    descriptions = [f.description for f in findings]
    assert any("Failing test" in d for d in descriptions)
    assert any("below the 50.0% floor" in d for d in descriptions)


def test_returns_none_when_zero_tests_collected(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pytest-cov",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "failures": [],
            "coverage_percent": None,
        },
        exit_code=5,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_unit_test_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None
