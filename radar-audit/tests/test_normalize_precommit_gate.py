# tests/test_normalize_precommit_gate.py
import pytest
from radar_audit.normalizers.precommit_gate import normalize_precommit_gate
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
        db_session, methodology_version.id, "Code quality", "Pre-commit quality gate"
    )
    return audit, scoring_run, criterion


def _stack_evidence(audit_id, tool_name, subproject_path):
    return ToolResult(
        audit_id=audit_id,
        tool_name=tool_name,
        tool_version="1.0.0",
        subproject_path=subproject_path,
        command="stub",
        raw_output={},
        exit_code=0,
        duration_ms=5,
    )


def _gate_result(audit_id, tier, entries):
    return ToolResult(
        audit_id=audit_id,
        tool_name="pre-commit-gate",
        tool_version="1.0.0",
        subproject_path=".",
        command="stub",
        raw_output={"tier": tier, "entries": entries},
        exit_code=0,
        duration_ms=5,
    )


def test_returns_none_when_no_precommit_gate_tool_result(db_session):
    audit, scoring_run, criterion = _setup(db_session)

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [])

    assert score is None


def test_returns_none_when_no_domains_detected(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    gate = _gate_result(audit.id, "none", [])
    db_session.add(gate)
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [gate])

    assert score is None


def test_scores_zero_when_tier_is_none_and_backend_domain_present(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "ruff-check", "backend")
    gate = _gate_result(audit.id, "none", [])
    db_session.add_all([backend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [backend_evidence, gate])

    assert score is not None
    assert score.value == 0.0
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 3
    assert {f.description for f in findings} == {
        "No pre-commit lint hook covers backend",
        "No pre-commit format hook covers backend",
        "No pre-commit type-check hook covers backend",
    }


def test_scores_ten_when_all_backend_cells_covered(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "ruff-check", "backend")
    gate = _gate_result(
        audit.id,
        "pre-commit",
        [
            {"id": "ruff", "files": None},
            {"id": "ruff-format", "files": None},
            {"id": "mypy", "files": None},
        ],
    )
    db_session.add_all([backend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [backend_evidence, gate])

    assert score is not None
    assert score.value == 10.0
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 0


def test_scores_partial_and_adds_findings_for_uncovered_cells(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "ruff-check", "backend")
    gate = _gate_result(audit.id, "pre-commit", [{"id": "ruff", "files": None}])
    db_session.add_all([backend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [backend_evidence, gate])

    assert score is not None
    assert score.value == pytest.approx(10 / 3)
    assert score.confidence == Confidence.HIGH
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 2
    assert {f.description for f in findings} == {
        "No pre-commit format hook covers backend",
        "No pre-commit type-check hook covers backend",
    }


def test_confidence_is_low_when_lefthook_path_was_used(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    frontend_evidence = _stack_evidence(audit.id, "eslint", "frontend")
    gate = _gate_result(audit.id, "lefthook", [{"id": "eslint", "files": None}])
    db_session.add_all([frontend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [frontend_evidence, gate])

    assert score is not None
    assert score.confidence == Confidence.LOW
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 2
    assert all(f.confidence == Confidence.LOW for f in findings)


def test_husky_domain_split_via_directory_scoped_files_pattern(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "ruff-check", "backend")
    frontend_evidence = _stack_evidence(audit.id, "tsc", "frontend")
    gate = _gate_result(
        audit.id,
        "husky",
        [
            {"id": "eslint", "files": "backend/**/*.js"},
            {"id": "eslint", "files": "frontend/**/*.js"},
        ],
    )
    db_session.add_all([backend_evidence, frontend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(
        db_session, scoring_run, criterion, [backend_evidence, frontend_evidence, gate]
    )

    assert score is not None
    assert score.value == pytest.approx(2 / 6 * 10)
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 4
    assert {f.description for f in findings} == {
        "No pre-commit format hook covers backend",
        "No pre-commit type-check hook covers backend",
        "No pre-commit format hook covers frontend",
        "No pre-commit type-check hook covers frontend",
    }


def test_pint_covers_both_lint_and_format_for_php_backend(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "phpstan", "backend")
    gate = _gate_result(audit.id, "pre-commit", [{"id": "pint", "files": None}])
    db_session.add_all([backend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [backend_evidence, gate])

    assert score is not None
    assert score.value == pytest.approx(2 / 3 * 10)
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 1
    assert findings[0].description == "No pre-commit type-check hook covers backend"


def test_unrecognized_hook_id_is_ignored(db_session):
    audit, scoring_run, criterion = _setup(db_session)
    backend_evidence = _stack_evidence(audit.id, "ruff-check", "backend")
    gate = _gate_result(audit.id, "pre-commit", [{"id": "some-custom-local-hook", "files": None}])
    db_session.add_all([backend_evidence, gate])
    db_session.commit()

    score = normalize_precommit_gate(db_session, scoring_run, criterion, [backend_evidence, gate])

    assert score is not None
    assert score.value == 0.0
    findings = db_session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    assert len(findings) == 3
