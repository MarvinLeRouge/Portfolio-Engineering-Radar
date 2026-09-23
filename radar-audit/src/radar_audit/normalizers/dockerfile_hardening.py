from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_dockerfile_hardening(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "hadolint"]
    if not relevant:
        return None

    clean = 0
    total = 0
    for tool_result in relevant:
        for entry in tool_result.raw_output.get("dockerfiles", []):
            total += 1
            findings = entry.get("findings", [])
            if not findings:
                clean += 1
                continue
            for finding in findings:
                session.add(
                    Finding(
                        scoring_run_id=scoring_run.id,
                        criterion_id=criterion.id,
                        tool_result_id=tool_result.id,
                        severity=FindingSeverity.LOW,
                        description=f"{finding['code']}: {finding['message']}",
                        file=entry["path"],
                        line=finding.get("line"),
                        confidence=Confidence.HIGH,
                        status=FindingStatus.OPEN,
                        human_verdict=HumanVerdict.UNREVIEWED,
                    )
                )

    if total == 0:
        return None

    # Score calculation: (clean / total) * 10 is provisional pending Phase 5
    # portfolio-wide calibration
    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(clean / total) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
