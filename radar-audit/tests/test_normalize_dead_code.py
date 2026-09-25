from radar_audit.normalizers.dead_code import normalize_dead_code
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
        db_session, methodology_version.id, "Maintainability", "Dead code / unused exports"
    )
    return audit, scoring_run, criterion


def _vulture_result(audit, count, exit_code=0):
    findings = [
        {"file": "src/a.py", "line": i, "kind": "function", "name": f"f{i}", "confidence": 60}
        for i in range(count)
    ]
    return ToolResult(
        audit_id=audit.id,
        tool_name="vulture",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"findings": findings},
        exit_code=exit_code,
        duration_ms=10,
    )


def _knip_result(audit, export_count):
    exports = [{"name": f"e{i}", "line": i, "col": 1, "pos": 0} for i in range(export_count)]
    issues = [{"file": "src/helpers.js", "exports": exports}] if export_count else []
    return ToolResult(
        audit_id=audit.id,
        tool_name="knip",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={"issues": issues},
        exit_code=0 if export_count == 0 else 1,
        duration_ms=10,
    )


def _phpmd_result(audit, unusedcode_count):
    violations = [{"ruleset": "codesize", "file": "src/a.php", "line": 1, "complexity": 3}]
    violations.extend(
        {"ruleset": "unusedcode", "file": "src/a.php", "line": i, "rule": "UnusedLocalVariable"}
        for i in range(unusedcode_count)
    )
    return ToolResult(
        audit_id=audit.id,
        tool_name="phpmd-codesize",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"violations": violations},
        exit_code=2 if unusedcode_count else 0,
        duration_ms=10,
    )


def test_scores_ten_when_no_dead_code(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_eight_at_three_findings(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 3, exit_code=3)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0


def test_scores_six_at_four_findings(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 4, exit_code=3)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 6.0


def test_scores_four_at_nine_findings(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 9, exit_code=3)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 4.0


def test_scores_two_above_fifteen_findings(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 16, exit_code=3)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0


def test_counts_knip_exports_only_not_dependency_issues(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="knip",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={
            "issues": [
                {
                    "file": "src/helpers.js",
                    "exports": [{"name": "unusedExport", "line": 5, "col": 1, "pos": 0}],
                    "dependencies": [{"name": "left-pad"}],
                    "unlisted": [{"name": "lodash"}],
                }
            ]
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0  # 1 dead-code item (export), dependency/unlisted entries excluded


def test_counts_phpmd_unusedcode_violations_only(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _phpmd_result(audit, 2)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0  # 2 unusedcode violations, codesize entry excluded from the count


def test_confidence_is_high_for_knip_and_medium_for_vulture_and_phpmd(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    knip_result = _knip_result(audit, 0)
    vulture_result = _vulture_result(audit, 0)
    db_session.add(knip_result)
    db_session.add(vulture_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [knip_result])
    assert score is not None
    assert score.confidence == Confidence.HIGH

    score = normalize_dead_code(db_session, scoring_run, criterion, [vulture_result])
    assert score is not None
    assert score.confidence == Confidence.MEDIUM


def test_creates_one_finding_per_dead_code_item(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _vulture_result(audit, 3, exit_code=3)
    db_session.add(tool_result)
    db_session.commit()

    normalize_dead_code(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 3


def test_worst_of_two_tool_results_wins(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    clean_result = _vulture_result(audit, 0)
    bad_result = _phpmd_result(audit, 9)
    db_session.add(clean_result)
    db_session.add(bad_result)
    db_session.commit()

    score = normalize_dead_code(db_session, scoring_run, criterion, [clean_result, bad_result])

    assert score is not None
    assert score.value == 4.0


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_dead_code(db_session, scoring_run, criterion, [])

    assert score is None
