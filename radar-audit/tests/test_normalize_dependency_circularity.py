from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import ScoreLevel
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
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Dependency direction / circularity",
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


def test_no_cycles_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {"modules": [{"source": "a.js", "dependencies": []}]},
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.level == ScoreLevel.CRITERION
    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_one_dependency_cruiser_cycle_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {
            "modules": [
                {
                    "source": "a.js",
                    "dependencies": [{"resolved": "b.js", "circular": True}],
                },
                {
                    "source": "b.js",
                    "dependencies": [{"resolved": "a.js", "circular": True}],
                },
            ]
        },
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].tool_result_id == tool_result.id


def test_pydeps_cycle_is_detected_via_dfs(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pydeps",
        {
            "mypkg": {"imported_by": ["mypkg.a", "mypkg.b"]},
            "mypkg.a": {"imports": ["mypkg", "mypkg.b"], "imported_by": ["mypkg.b"]},
            "mypkg.b": {"imports": ["mypkg", "mypkg.a"], "imported_by": ["mypkg.a"]},
        },
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_worst_band_wins_across_two_subprojects(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    clean = _make_tool_result(
        db_session,
        audit,
        "dependency-cruiser",
        {"modules": [{"source": "a.js", "dependencies": []}]},
        subproject_path="frontend",
    )
    broken = _make_tool_result(
        db_session,
        audit,
        "pydeps",
        {
            "mypkg": {"imported_by": ["mypkg.a", "mypkg.b", "mypkg.c"]},
            "mypkg.a": {"imports": ["mypkg.b"], "imported_by": []},
            "mypkg.b": {"imports": ["mypkg.c"], "imported_by": ["mypkg.a"]},
            "mypkg.c": {"imports": ["mypkg.a"], "imported_by": ["mypkg.b"]},
        },
        subproject_path="backend",
    )

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [clean, broken])

    # broken has exactly one cycle group (a 3-node cycle a->b->c->a) -> band 6.0
    # (1-2 cycles); worst wins over clean's 10
    assert score.value == 6.0


def test_skips_failed_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    failed = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="pydeps",
        tool_version="1.0.0",
        command="stub",
        raw_output={"error": "crashed"},
        exit_code=-1,
        duration_ms=0,
    )
    db_session.add(failed)
    db_session.commit()
    db_session.refresh(failed)

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [failed])

    assert score is None


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    unrelated = _make_tool_result(db_session, audit, "design-doc-presence", {"found_path": None})

    score = normalize_dependency_circularity(db_session, scoring_run, criterion, [unrelated])

    assert score is None
