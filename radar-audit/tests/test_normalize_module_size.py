from radar_audit.normalizers.module_size import normalize_module_size
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
        db_session, methodology_version.id, "Architecture & design", "Module size distribution"
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


def test_all_modules_covered_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}, "b.py": {"sloc": 200}}
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_one_oversized_module_creates_a_finding_and_lowers_score(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}, "big.py": {"sloc": 500}}
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 5.0  # 1 covered / 2 applicable * 10
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "big.py"


def test_covered_and_applicable_are_summed_across_two_subprojects(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    radon_result = _make_tool_result(
        db_session, audit, "radon-raw", {"a.py": {"sloc": 100}}, subproject_path="backend"
    )
    static_result = _make_tool_result(
        db_session,
        audit,
        "static-loc-count",
        {"files": {"a.js": 100, "b.js": 500}},
        subproject_path="frontend",
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [radon_result, static_result])

    assert score.value == pytest_approx(20.0 / 3)


def pytest_approx(value):
    import pytest

    return pytest.approx(value)


def test_zero_applicable_modules_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, "static-loc-count", {"files": {}})

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score is None
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_returns_none_when_no_relevant_tool_results(db_session):
    _, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    score = normalize_module_size(db_session, scoring_run, criterion, [])

    assert score is None


def test_radon_error_entries_are_excluded_not_crashed_on(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "radon-raw",
        {"a.py": {"sloc": 100}, "unparseable.py": {"error": "SyntaxError: invalid syntax"}},
    )

    score = normalize_module_size(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0  # only a.py counted, 1/1 covered
