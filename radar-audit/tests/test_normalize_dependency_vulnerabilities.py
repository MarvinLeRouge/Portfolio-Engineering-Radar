from radar_audit.normalizers.dependency_vulnerabilities import (
    normalize_dependency_vulnerabilities,
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
        db_session, methodology_version.id, "Security", "Dependency vulnerabilities (CVE)"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, tool_name, raw_output, subproject_path="."):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=subproject_path,
        tool_name=tool_name,
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


def test_no_manifest_found_anywhere_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, "pip-audit", {"manifest_found": False})

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_clean_manifest_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "pip-audit", {"manifest_found": True, "vulnerabilities": []}
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_medium_severity_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pip-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {
                    "id": "PYSEC-2020-96",
                    "package": "pyyaml",
                    "severity": "MEDIUM",
                    "fix_available": True,
                }
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].tool_result_id == tool_result.id


def test_high_severity_scores_four(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pnpm-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {"id": "1", "package": "lodash", "severity": "HIGH", "fix_available": True}
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0


def test_critical_severity_scores_two(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "composer-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {
                    "id": "PKSA-x",
                    "package": "phpmailer/phpmailer",
                    "severity": "CRITICAL",
                    "fix_available": True,
                }
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0


def test_worst_severity_wins_across_multiple_subprojects_and_tools(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    clean = _make_tool_result(
        db_session,
        audit,
        "pip-audit",
        {"manifest_found": True, "vulnerabilities": []},
        subproject_path="backend",
    )
    critical = _make_tool_result(
        db_session,
        audit,
        "pnpm-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {"id": "1", "package": "x", "severity": "CRITICAL", "fix_available": True}
            ],
        },
        subproject_path="frontend",
    )

    score = normalize_dependency_vulnerabilities(
        db_session, scoring_run, criterion, [clean, critical]
    )

    assert score.value == 2.0


def test_skips_tool_results_where_manifest_not_found(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    no_manifest = _make_tool_result(db_session, audit, "pip-audit", {"manifest_found": False})
    with_manifest = _make_tool_result(
        db_session, audit, "pnpm-audit", {"manifest_found": True, "vulnerabilities": []}
    )

    score = normalize_dependency_vulnerabilities(
        db_session, scoring_run, criterion, [no_manifest, with_manifest]
    )

    assert score.value == 10.0
