import pytest
from sqlalchemy.exc import IntegrityError

from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import ScoringRun


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="abc123", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    version = MethodologyVersion(version_label="1.0")
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    category = Category(methodology_version_id=version.id, name="Security", weight=1.5, order=4)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    criterion = Criterion(
        category_id=category.id,
        name="Secrets in tracked history",
        description="Gitleaks",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=version.id)
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    return scoring_run, criterion


def test_create_finding_with_evidence_and_recommendation(db_session):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret in git history",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    assert finding.status == FindingStatus.OPEN
    assert finding.human_verdict == HumanVerdict.UNREVIEWED

    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.TOOL_OUTPUT_EXCERPT,
        content="gitleaks: generic-api-key at config.py:42",
    )
    recommendation = Recommendation(
        finding_id=finding.id, text="Rotate the credential and purge it from history."
    )
    db_session.add(evidence)
    db_session.add(recommendation)
    db_session.commit()

    assert evidence.score_id is None
    assert recommendation.finding_id == finding.id


def test_evidence_requires_exactly_one_parent(db_session):
    scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.LOW,
        description="minor",
        confidence=Confidence.LOW,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    db_session.add(
        Evidence(
            finding_id=finding.id,
            score_id=None,
            evidence_type=EvidenceType.HUMAN_CONFIRMATION,
            content="ok",
        )
    )
    db_session.commit()  # exactly one parent set, must succeed

    db_session.add(
        Evidence(
            finding_id=None,
            score_id=None,
            evidence_type=EvidenceType.HUMAN_CONFIRMATION,
            content="orphan",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
