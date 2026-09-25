from __future__ import annotations

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.cyclomatic_complexity import _extract_blocks

_USABLE_EXIT_CODES_BY_TOOL = {
    "radon-cc": {0},
    "eslint-complexity": {0, 1},
    "phpmd-codesize": {0, 2},
}
_OUTLIER_COMPLEXITY_THRESHOLD = 10
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (2, 8.0), (5, 6.0), (10, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_complexity_hotspots(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL.get(r.tool_name, set())
    ]
    if not relevant:
        return None

    worst_value: float | None = None
    worst_confidence: Confidence | None = None
    for tool_result in relevant:
        blocks = _extract_blocks(tool_result)
        outlier_count = sum(
            1 for block in blocks if int(block["complexity"]) > _OUTLIER_COMPLEXITY_THRESHOLD
        )
        value = _band_value(outlier_count)
        tool_confidence = _confidence_for_tool(tool_result.tool_name)
        if worst_value is None or value < worst_value:
            worst_value = value
            worst_confidence = tool_confidence

    if worst_value is None or worst_confidence is None:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=worst_value,
        confidence=worst_confidence,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(outlier_count: int) -> float:
    for max_count, value in _BANDS:
        if outlier_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _confidence_for_tool(tool_name: str) -> Confidence:
    return Confidence.HIGH if tool_name == "radon-cc" else Confidence.MEDIUM
