from radar_audit.normalizers.container_image_vulnerabilities import (
    normalize_container_image_vulnerabilities,
)
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
        db_session, methodology_version.id, "Security", "Container image vulnerabilities"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="trivy-image",
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


def test_no_image_found_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"image_found": False})

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score is None


def test_image_found_with_no_vulnerabilities_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"image_found": True, "image": "app:latest", "vulnerabilities": []}
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 10.0


def test_high_severity_vulnerability_scores_four_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "image_found": True,
            "image": "app:latest",
            "vulnerabilities": [
                {"id": "CVE-2024-1", "severity": "HIGH", "pkg": "openssl", "fix_version": "3.1"}
            ],
        },
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 4.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_critical_severity_vulnerability_scores_two(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "image_found": True,
            "image": "app:latest",
            "vulnerabilities": [
                {"id": "CVE-2024-2", "severity": "CRITICAL", "pkg": "libx", "fix_version": None}
            ],
        },
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 2.0
