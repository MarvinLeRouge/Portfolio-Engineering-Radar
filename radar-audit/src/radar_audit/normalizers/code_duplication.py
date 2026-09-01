from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Bands: <=3%->10, 3-5%->6, 5-10%->4, >10%->2 (spec §3.2). Resolved during
# design but provisional -- not yet calibrated against real portfolio data
# (spec §11), same discipline as 2.1's 30-line/400-LOC thresholds.
_BANDS: tuple[tuple[float, float], ...] = ((3.0, 10.0), (5.0, 6.0), (10.0, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_code_duplication(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "jscpd" and r.exit_code == 0]
    if not relevant:
        return None

    tool_result = relevant[0]
    percentage = tool_result.raw_output.get("statistics", {}).get("total", {}).get("percentage")
    if percentage is None:
        return None

    for duplicate in tool_result.raw_output.get("duplicates", []):
        first = duplicate["firstFile"]
        second = duplicate["secondFile"]
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=(
                    f"Duplicated block between {first['name']}:{first['start']}-{first['end']} "
                    f"and {second['name']}:{second['start']}-{second['end']}"
                ),
                file=first["name"],
                line=first["start"],
                confidence=Confidence.MEDIUM,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(percentage),
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(percentage: float) -> float:
    for max_percentage, value in _BANDS:
        if percentage <= max_percentage:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
