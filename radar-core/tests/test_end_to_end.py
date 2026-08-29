# radar-core/tests/test_end_to_end.py
from datetime import UTC

from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    RoadmapStatus,
    ScoreLevel,
    ScoringModel,
)
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Evidence, Finding, Recommendation
from radar_core.models.links import FindingImprovementTaskLink
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.roadmap import ImprovementTask, RoadmapItem
from radar_core.models.scoring import Score, ScoringRun
from radar_core.models.snapshot import Snapshot


def test_full_audit_to_roadmap_chain(db_session):
    repo = Repository(name="GeoChallenge-Tracker", path="/home/mlr/projets/GeoChallenge-Tracker")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    audit = Audit(repository_id=repo.id, commit_sha="deadbeef", is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="gitleaks",
        tool_version="8.18.0",
        command="gitleaks detect --report-format json",
        raw_output={"findings": [{"rule": "generic-api-key", "file": "config.py", "line": 42}]},
        exit_code=1,
        duration_ms=380,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)

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
        description="Gitleaks, git-history mode",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(criterion)
    db_session.commit()
    db_session.refresh(criterion)

    scoring_run = ScoringRun(
        audit_id=audit.id,
        methodology_version_id=version.id,
        global_score=2.0,
        global_confidence=Confidence.HIGH,
    )
    db_session.add(scoring_run)
    db_session.commit()
    db_session.refresh(scoring_run)

    finding = Finding(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        tool_result_id=tool_result.id,
        severity=FindingSeverity.CRITICAL,
        description="Confirmed secret in config.py",
        file="config.py",
        line=42,
        confidence=Confidence.HIGH,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    evidence = Evidence(
        finding_id=finding.id,
        evidence_type=EvidenceType.TOOL_OUTPUT_EXCERPT,
        content="gitleaks: generic-api-key at config.py:42",
    )
    recommendation = Recommendation(
        finding_id=finding.id, text="Rotate the credential and purge it from history."
    )
    criterion_score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=0.0,
        confidence=Confidence.HIGH,
    )
    db_session.add(evidence)
    db_session.add(recommendation)
    db_session.add(criterion_score)
    db_session.commit()

    task = ImprovementTask(title="Rotate leaked credential", description="See finding evidence.")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(FindingImprovementTaskLink(finding_id=finding.id, improvement_task_id=task.id))
    db_session.commit()

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

    snapshot = Snapshot(
        portfolio_global_score=2.0,
        portfolio_global_confidence=Confidence.HIGH,
        details={"repositories": [{"name": repo.name, "score": 2.0}]},
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    assert roadmap_item.status == RoadmapStatus.DONE
    assert roadmap_item.done_evidence_id == done_evidence.id
    assert finding.tool_result_id == tool_result.id

    # Every UTCDateTime column touched by this chain must round-trip as UTC-aware,
    # not silently regress to a naive datetime.
    for entity, field in (
        (version, "frozen_at"),
        (audit, "audited_at"),
        (tool_result, "ran_at"),
        (scoring_run, "scored_at"),
        (finding, "detected_at"),
        (evidence, "created_at"),
        (recommendation, "created_at"),
        (task, "created_at"),
        (roadmap_item, "promoted_at"),
        (snapshot, "taken_at"),
    ):
        value = getattr(entity, field)
        assert value.tzinfo is not None, f"{type(entity).__name__}.{field} lost its tzinfo"
        assert value.tzinfo == UTC, f"{type(entity).__name__}.{field} is not UTC"
