from radar_audit.normalizers.secrets_in_history import normalize_secrets_in_history
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence
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
        db_session, methodology_version.id, "Security", "Secrets in tracked history"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="gitleaks",
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


def test_no_findings_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"findings": []})

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_pre_filtered_test_fixture_hit_scores_eight_with_low_confidence(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_auth.py",
                    "line": 3,
                    "match": 'fake_token = "eyJhbGciOiJIUzI1NiJ9"',
                    "commit": "abc123",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].confidence == Confidence.LOW


def test_pre_filtered_env_example_hit_scores_eight(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": ".env.prod.example",
                    "line": 5,
                    "match": "BCRYPT_ROUNDS=12",
                    "commit": "def456",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0


def test_unfiltered_hit_scores_two_with_high_confidence(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "github-pat",
                    "file": "config.py",
                    "line": 1,
                    "match": 'API_KEY = "ghp_realtoken"',
                    "commit": "ghi789",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings[0].confidence == Confidence.HIGH


def test_one_unfiltered_hit_wins_over_several_pre_filtered_ones(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_auth.py",
                    "line": 1,
                    "match": 'fake_token = "x"',
                    "commit": "a",
                },
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_other.py",
                    "line": 1,
                    "match": 'mock_token = "y"',
                    "commit": "b",
                },
                {
                    "rule": "github-pat",
                    "file": "config.py",
                    "line": 1,
                    "match": 'API_KEY = "ghp_realtoken"',
                    "commit": "c",
                },
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0
