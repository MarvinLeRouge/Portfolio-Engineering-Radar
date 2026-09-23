from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_SEVERITY_ENUM = {"HIGH": FindingSeverity.HIGH, "CRITICAL": FindingSeverity.CRITICAL}
# Trivy is invoked with --severity HIGH,CRITICAL (per toolchain.md), so only these
# two rows of the band table are ever reachable -- provisional pending Phase 5
# portfolio-wide calibration, per the category-4 spec's §3.1.
_BAND_VALUE = {"NONE": 10.0, "HIGH": 4.0, "CRITICAL": 2.0}
_SEVERITY_RANK = {"NONE": 0, "HIGH": 1, "CRITICAL": 2}


def normalize_container_image_vulnerabilities(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "trivy-image" and r.raw_output.get("image_found") is True
    ]
    if not relevant:
        return None

    worst = "NONE"
    for tool_result in relevant:
        for vuln in tool_result.raw_output.get("vulnerabilities", []):
            severity = vuln.get("severity", "HIGH")
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=_SEVERITY_ENUM.get(severity, FindingSeverity.HIGH),
                    description=f"{vuln['id']}: {vuln['pkg']}",
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
            if _SEVERITY_RANK.get(severity, 1) > _SEVERITY_RANK[worst]:
                worst = severity

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_BAND_VALUE[worst],
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
