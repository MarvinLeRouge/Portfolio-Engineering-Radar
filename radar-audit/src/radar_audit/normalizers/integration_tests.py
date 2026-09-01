from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_integration_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.tool_name == "integration-test-heuristic" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    total = tool_result.raw_output.get("total_test_files", 0)
    if total == 0:
        # No tests at all is already carried by criterion 3.1 -- not penalized twice.
        return None

    integration = tool_result.raw_output.get("integration_test_files", 0)
    ratio_percent = (integration / total) * 100

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_band_value(ratio_percent),
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(ratio_percent: float) -> float:
    # Bands: 0%->0, 0-10%->4, 10-25%->6, 25-50%->8, >50%->10 (spec §3.4). Resolved
    # during design but provisional -- not yet calibrated against real portfolio data
    # (spec §11), same discipline as every prior increment's thresholds.
    if ratio_percent <= 0.0:
        return 0.0
    if ratio_percent <= 10.0:
        return 4.0
    if ratio_percent <= 25.0:
        return 6.0
    if ratio_percent <= 50.0:
        return 8.0
    return 10.0
