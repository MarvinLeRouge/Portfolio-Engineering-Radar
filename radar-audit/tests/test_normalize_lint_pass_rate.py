from radar_audit.normalizers.lint_pass_rate import normalize_lint_pass_rate
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_audit(db_session):
    repo = Repository(name="fixture", path="/tmp/fixture")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def _setup(db_session):
    audit = _make_audit(db_session)
    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Code quality", "Linter clean pass rate"
    )
    return audit, scoring_run, criterion


def test_scores_ten_when_ruff_is_fully_clean(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ruff-check",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"violations": [], "total_files": 3},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_lowers_score_and_adds_findings_for_ruff_violations(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="ruff-check",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "violations": [
                {
                    "filename": "a.py",
                    "code": "F401",
                    "message": "unused import",
                    "location": {"row": 1, "column": 1},
                },
            ],
            "total_files": 2,
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 5.0  # 1 covered / 2 applicable * 10
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1
    assert findings[0].file == "a.py"


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [])

    assert score is None


def test_scores_ten_when_pint_passes(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pint",
        tool_version="1.30.5",
        subproject_path="laravel",
        command="stub",
        raw_output={"result": "passed"},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_lowers_score_and_adds_findings_for_pint_failures(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="pint",
        tool_version="1.30.5",
        subproject_path="laravel",
        command="stub",
        raw_output={
            "tool": "pint",
            "result": "fail",
            "files": [{"path": "src/A.php", "fixers": ["single_line_empty_body"]}],
        },
        exit_code=1,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_lint_pass_rate(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 0.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1
    assert findings[0].file == "src/A.php"
