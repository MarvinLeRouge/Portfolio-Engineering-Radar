from radar_audit.normalizers.dockerfile_hardening import normalize_dockerfile_hardening
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
        db_session, methodology_version.id, "Security", "Dockerfile hardening"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output, exit_code=0):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="hadolint",
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


def test_no_dockerfiles_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"dockerfiles": []})

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_one_clean_dockerfile_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"dockerfiles": [{"path": "Dockerfile", "findings": []}]}
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_one_dirty_dockerfile_of_two_scores_five_and_creates_findings(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "findings": []},
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {
                            "code": "DL3008",
                            "column": 1,
                            "file": "-",
                            "level": "warning",
                            "line": 2,
                            "message": "Pin versions in apt get install",
                        }
                    ],
                },
            ]
        },
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 5.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "backend/Dockerfile"
    assert findings[0].line == 2


def test_orchestrator_crash_record_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    crashed = _make_tool_result(
        db_session, audit, {"error": "Command 'docker' timed out after 120 seconds"}, exit_code=-1
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [crashed])

    assert score is None


def test_all_dockerfiles_failed_to_lint_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {"dockerfiles": [{"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"}]},
        exit_code=1,
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_failed_dockerfile_is_excluded_from_the_ratio(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "error": "Cannot connect to the Docker daemon"},
                {"path": "frontend/Dockerfile", "findings": []},
            ]
        },
        exit_code=1,
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
