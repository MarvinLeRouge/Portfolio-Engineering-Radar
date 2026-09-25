from radar_audit.normalizers.docstring_coverage import normalize_docstring_coverage
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence
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
        "Maintainability",
        "Documentation-in-code (docstring/comment coverage)",
    )
    return audit, scoring_run, criterion


def _docvet_result(audit, percentage, findings=None):
    return ToolResult(
        audit_id=audit.id,
        tool_name="docvet",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "findings": findings or [],
            "presence_coverage": {
                "documented": 0,
                "total": 1,
                "percentage": percentage,
                "threshold": 0.0,
                "passed": True,
            },
        },
        exit_code=0,
        duration_ms=10,
    )


def _phpdoc_checker_result(audit, errors_count, exit_code=1):
    findings = [
        {"type": "class", "file": "A.php", "class": f"\\C{i}", "line": i}
        for i in range(errors_count)
    ]
    return ToolResult(
        audit_id=audit.id,
        tool_name="phpdoc-checker",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"findings": findings},
        exit_code=exit_code,
        duration_ms=10,
    )


def test_python_scores_percentage_over_ten(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _docvet_result(audit, 80.0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0


def test_python_creates_a_finding_per_docvet_finding(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _docvet_result(
        audit,
        50.0,
        findings=[
            {
                "file": "src/a.py",
                "line": 6,
                "symbol": "subtract",
                "rule": "missing-docstring",
                "message": "Public function has no docstring",
                "category": "required",
                "severity": "high",
            }
        ],
    )
    db_session.add(tool_result)
    db_session.commit()

    normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1
    assert findings[0].file == "src/a.py"


def test_php_scores_ten_with_no_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpdoc_checker_result(audit, 0, exit_code=0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_php_scores_eight_at_five_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpdoc_checker_result(audit, 5)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0


def test_php_scores_six_at_six_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpdoc_checker_result(audit, 6)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 6.0


def test_php_scores_four_at_sixteen_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpdoc_checker_result(audit, 16)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 4.0


def test_php_scores_two_above_thirty_errors(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpdoc_checker_result(audit, 31)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0


def test_php_only_counts_class_and_method_types_not_param_missing(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="phpdoc-checker",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "findings": [
                {"type": "class", "file": "A.php", "class": "\\A", "line": 1},
                {
                    "type": "param-missing",
                    "file": "A.php",
                    "class": "\\A",
                    "method": "m",
                    "line": 5,
                    "param": "$a",
                },
                {
                    "type": "return-missing",
                    "file": "A.php",
                    "class": "\\A",
                    "method": "m",
                    "line": 5,
                },
            ]
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0  # only the 1 "class" finding counts; 1-5 band


def test_worst_of_python_and_php_wins(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    good_python = _docvet_result(audit, 100.0)
    bad_php = _phpdoc_checker_result(audit, 31)
    db_session.add(good_python)
    db_session.add(bad_php)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [good_python, bad_php])

    assert score is not None
    assert score.value == 2.0


def test_confidence_is_medium_for_both_stacks(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _docvet_result(audit, 100.0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.MEDIUM


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [])

    assert score is None


def test_returns_none_when_docvet_result_has_no_usable_payload(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="docvet",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"stdout": "", "stderr": "No Python files to check."},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_docstring_coverage(db_session, scoring_run, criterion, [tool_result])

    assert score is None
