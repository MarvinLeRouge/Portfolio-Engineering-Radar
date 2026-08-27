from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    RoadmapStatus,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Evidence, Finding
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import ScoringRun


def _make_finding(db_session) -> Finding:
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

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret",
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_improvement_task_links_to_finding_via_association_table(db_session):
    finding = _make_finding(db_session)

    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

    link = db_session.get(FindingImprovementTaskLink, (finding.id, task.id))
    assert link is not None


def test_improvement_task_is_not_a_roadmap_item_until_promoted(db_session):
    _make_finding(db_session)
    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    from sqlmodel import select

    assert (
        db_session.exec(
            select(RoadmapItem).where(RoadmapItem.improvement_task_id == task.id)
        ).first()
        is None
    )


def test_roadmap_item_promotion_with_done_evidence(db_session):
    finding = _make_finding(db_session)
    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    roadmap_item = RoadmapItem(improvement_task_id=task.id, status=RoadmapStatus.TODO, priority=1)
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)

    done_evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.HUMAN_CONFIRMATION,
        content="Credential rotated and purged, confirmed by developer.",
    )
    db_session.add(done_evidence)
    db_session.commit()
    db_session.refresh(done_evidence)

    roadmap_item.status = RoadmapStatus.DONE
    roadmap_item.done_evidence_id = done_evidence.id
    db_session.add(roadmap_item)
    db_session.commit()
    db_session.refresh(roadmap_item)

    assert roadmap_item.status == RoadmapStatus.DONE
    assert roadmap_item.done_evidence_id == done_evidence.id
