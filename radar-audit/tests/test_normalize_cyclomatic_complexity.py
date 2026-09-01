from radar_audit.normalizers.cyclomatic_complexity import normalize_cyclomatic_complexity
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
        db_session, methodology_version.id, "Code quality", "Cyclomatic complexity"
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_radon_worst_complexity_is_low(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="radon-cc",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "src/a.py": [{"type": "function", "name": "add", "complexity": 3, "rank": "A"}]
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_finding_and_score_confidence_is_high_for_radon(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="radon-cc",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "src/a.py": [{"type": "function", "name": "classify", "complexity": 35, "rank": "F"}]
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert findings[0].confidence == Confidence.HIGH


def test_finding_and_score_confidence_is_medium_for_eslint_complexity(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="eslint-complexity",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={"complexities": [{"file": "src/a.js", "line": 1, "complexity": 35}]},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.confidence == Confidence.MEDIUM
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert findings[0].confidence == Confidence.MEDIUM


def test_scores_low_and_adds_a_finding_when_worst_complexity_is_very_high(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="radon-cc",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "src/a.py": [{"type": "function", "name": "classify", "complexity": 35, "rank": "F"}]
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [])

    assert score is None


def test_counts_eslint_complexity_result_with_exit_code_one(db_session):
    # eslint-complexity is configured with `complexity: ["error", 0]`, so on a
    # real repo it exits 1 whenever it finds any function at all -- exit 1 is
    # its normal "ran fine, found data" outcome, not a failure.
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="eslint-complexity",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={"complexities": [{"file": "src/a.js", "line": 1, "complexity": 3}]},
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_counts_phpmd_codesize_result_with_exit_code_two(db_session):
    # phpmd's codesize ruleset exits 2 (not 1) when it finds violations,
    # reserving 0 for a clean scan -- confirmed against a real repo.
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="phpmd-codesize",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"violations": [{"file": "src/a.php", "line": 18, "complexity": 12}]},
        exit_code=2,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 6.0


def test_ignores_phpmd_codesize_result_with_exit_code_one(db_session):
    # exit 1 is not part of phpmd's own 0/2 convention (0=clean, 2=violations),
    # so a phpmd-codesize result with exit_code=1 must be treated as unusable.
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="phpmd-codesize",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"violations": [{"file": "src/a.php", "line": 18, "complexity": 12}]},
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_cyclomatic_complexity(db_session, scoring_run, criterion, [tool_result])

    assert score is None
