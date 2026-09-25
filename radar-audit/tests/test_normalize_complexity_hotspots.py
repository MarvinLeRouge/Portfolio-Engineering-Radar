from radar_audit.normalizers.complexity_hotspots import normalize_complexity_hotspots
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
        db_session, methodology_version.id, "Maintainability", "Complexity hotspots"
    )
    return audit, scoring_run, criterion


def _radon_result(audit, blocks):
    return ToolResult(
        audit_id=audit.id,
        tool_name="radon-cc",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={"src/a.py": blocks},
        exit_code=0,
        duration_ms=10,
    )


def test_scores_ten_when_no_blocks_exceed_the_threshold(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _radon_result(
        audit, [{"type": "function", "name": "add", "complexity": 3, "rank": "A"}]
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_scores_eight_at_two_outliers(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    blocks = [
        {"type": "function", "name": f"f{i}", "complexity": 15, "rank": "D"} for i in range(2)
    ]
    tool_result = _radon_result(audit, blocks)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 8.0


def test_scores_six_at_three_outliers(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    blocks = [
        {"type": "function", "name": f"f{i}", "complexity": 15, "rank": "D"} for i in range(3)
    ]
    tool_result = _radon_result(audit, blocks)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 6.0


def test_scores_four_at_six_outliers(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    blocks = [
        {"type": "function", "name": f"f{i}", "complexity": 15, "rank": "D"} for i in range(6)
    ]
    tool_result = _radon_result(audit, blocks)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 4.0


def test_scores_two_above_ten_outliers(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    blocks = [
        {"type": "function", "name": f"f{i}", "complexity": 15, "rank": "D"} for i in range(11)
    ]
    tool_result = _radon_result(audit, blocks)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 2.0


def test_confidence_is_high_for_radon_and_medium_for_eslint(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    radon_result = _radon_result(
        audit, [{"type": "function", "name": "f", "complexity": 3, "rank": "A"}]
    )
    eslint_result = ToolResult(
        audit_id=audit.id,
        tool_name="eslint-complexity",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={"complexities": [{"file": "src/a.js", "line": 1, "complexity": 3}]},
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(radon_result)
    db_session.add(eslint_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [eslint_result])
    assert score is not None
    assert score.confidence == Confidence.MEDIUM

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [radon_result])
    assert score is not None
    assert score.confidence == Confidence.HIGH


def test_filters_phpmd_violations_to_codesize_only(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = ToolResult(
        audit_id=audit.id,
        tool_name="phpmd-codesize",
        tool_version="1.0.0",
        subproject_path="backend",
        command="stub",
        raw_output={
            "violations": [
                {"ruleset": "codesize", "file": "src/a.php", "line": 18, "complexity": 15},
                {
                    "ruleset": "unusedcode",
                    "file": "src/a.php",
                    "line": 7,
                    "rule": "UnusedLocalVariable",
                },
            ]
        },
        exit_code=2,
        duration_ms=10,
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert (
        score.value == 8.0
    )  # 1 codesize outlier -> 1-2 band, not crashing on the unusedcode entry


def test_worst_of_two_tool_results_wins(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    clean_result = _radon_result(
        audit, [{"type": "function", "name": "f", "complexity": 3, "rank": "A"}]
    )
    bad_result = ToolResult(
        audit_id=audit.id,
        tool_name="eslint-complexity",
        tool_version="1.0.0",
        subproject_path="frontend",
        command="stub",
        raw_output={
            "complexities": [{"file": "src/a.js", "line": i, "complexity": 15} for i in range(6)]
        },
        exit_code=0,
        duration_ms=10,
    )
    db_session.add(clean_result)
    db_session.add(bad_result)
    db_session.commit()

    score = normalize_complexity_hotspots(
        db_session, scoring_run, criterion, [clean_result, bad_result]
    )

    assert score is not None
    assert score.value == 4.0


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [])

    assert score is None


def test_creates_no_finding_rows(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _radon_result(
        audit, [{"type": "function", "name": "f", "complexity": 35, "rank": "F"}]
    )
    db_session.add(tool_result)
    db_session.commit()

    normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert findings == []


def _tool_result(audit, tool_name, raw_output, exit_code):
    return ToolResult(
        audit_id=audit.id,
        tool_name=tool_name,
        tool_version="1.0.0",
        subproject_path="sub",
        command="stub",
        raw_output=raw_output,
        exit_code=exit_code,
        duration_ms=10,
    )


def test_returns_none_for_eslint_fallback_payload_instead_of_a_perfect_ten(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    # npx failure: exit 1 (a usable code for eslint) but no "complexities" key.
    tool_result = _tool_result(
        audit, "eslint-complexity", {"stdout": "", "stderr": "npm ERR! network"}, 1
    )
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_for_radon_fallback_payload(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit, "radon-cc", {"stdout": "garbage", "stderr": ""}, 0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_returns_none_for_phpmd_parse_failure_payload(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    tool_result = _tool_result(audit, "phpmd-codesize", {"violations": [], "stdout": "not xml"}, 0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_scores_ten_for_eslint_run_with_empty_complexities(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    # Key present but empty: eslint really ran and found no functions.
    tool_result = _tool_result(audit, "eslint-complexity", {"complexities": []}, 0)
    db_session.add(tool_result)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [tool_result])

    assert score is not None
    assert score.value == 10.0


def test_unusable_result_does_not_mask_a_usable_one(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    unusable = _tool_result(audit, "eslint-complexity", {"stdout": "", "stderr": ""}, 1)
    usable = _radon_result(
        audit,
        [{"type": "function", "name": f"f{i}", "complexity": 15, "rank": "C"} for i in range(3)],
    )
    db_session.add(unusable)
    db_session.add(usable)
    db_session.commit()

    score = normalize_complexity_hotspots(db_session, scoring_run, criterion, [unusable, usable])

    assert score is not None
    assert score.value == 6.0
    assert score.confidence == Confidence.HIGH
