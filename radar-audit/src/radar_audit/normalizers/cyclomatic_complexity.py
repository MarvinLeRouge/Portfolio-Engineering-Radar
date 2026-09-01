from __future__ import annotations

from typing import Any

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Each tool's own convention for "ran successfully and produced usable
# data" differs (confirmed against a real portfolio repo in Task 17):
# radon-cc always exits 0; eslint-complexity is configured with
# `complexity: ["error", 0]` so it exits 1 on virtually every real file
# with a function; phpmd's codesize ruleset exits 2 (not 1) when it finds
# violations, reserving 0 for a clean scan.
_USABLE_EXIT_CODES_BY_TOOL = {
    "radon-cc": {0},
    "eslint-complexity": {0, 1},
    "phpmd-codesize": {0, 2},
}
_RELEVANT_TOOLS = set(_USABLE_EXIT_CODES_BY_TOOL)
# Bands: <=10->10, 11-20->6, 21-30->4, >30->2 (spec §3.3). Resolved during
# design but provisional -- not yet calibrated against real portfolio data
# (spec §11), same discipline as 2.1's 30-line/400-LOC thresholds.
_BANDS: tuple[tuple[int, float], ...] = ((10, 10.0), (20, 6.0), (30, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0
_WORST_COMPLEXITY_THRESHOLD_FOR_FINDING = 10


def normalize_cyclomatic_complexity(
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
        if not blocks:
            continue
        tool_confidence = _confidence_for_tool(tool_result.tool_name)
        worst_block = max(blocks, key=lambda b: int(b["complexity"]))
        if int(worst_block["complexity"]) > _WORST_COMPLEXITY_THRESHOLD_FOR_FINDING:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.MEDIUM,
                    description=(
                        f"{worst_block.get('name', 'function')} has cyclomatic complexity "
                        f"{worst_block['complexity']}"
                    ),
                    file=worst_block.get("file"),
                    line=worst_block.get("line"),
                    confidence=tool_confidence,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
        value = _band_value(int(worst_block["complexity"]))
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


def _band_value(complexity: int) -> float:
    for max_complexity, value in _BANDS:
        if complexity <= max_complexity:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _confidence_for_tool(tool_name: str) -> Confidence:
    # radon is validated (spec §9); the JS/PHP candidates stay MEDIUM until
    # smoke-tested against a real repo (Task 17).
    return Confidence.HIGH if tool_name == "radon-cc" else Confidence.MEDIUM


def _extract_blocks(tool_result: ToolResult) -> list[dict[str, Any]]:
    if tool_result.tool_name == "radon-cc":
        blocks = []
        for file_path, entries in tool_result.raw_output.items():
            for entry in entries:
                blocks.append(
                    {
                        "complexity": entry["complexity"],
                        "name": entry["name"],
                        "file": file_path,
                        "line": entry.get("lineno"),
                    }
                )
        return blocks
    if tool_result.tool_name == "eslint-complexity":
        return [
            {"complexity": c["complexity"], "name": None, "file": c["file"], "line": c["line"]}
            for c in tool_result.raw_output.get("complexities", [])
        ]
    return [
        {"complexity": v["complexity"], "name": None, "file": v["file"], "line": v["line"]}
        for v in tool_result.raw_output.get("violations", [])
    ]
