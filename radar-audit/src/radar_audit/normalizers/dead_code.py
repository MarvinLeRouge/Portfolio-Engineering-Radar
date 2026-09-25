from __future__ import annotations

from typing import Any

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_USABLE_EXIT_CODES_BY_TOOL = {
    "vulture": {0, 3},
    "knip": {0, 1},
    "phpmd-codesize": {0, 2},
}
_KNIP_UNUSED_SYMBOL_CATEGORIES = ("exports", "types", "enumMembers")
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (3, 8.0), (8, 6.0), (15, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_dead_code(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL.get(r.tool_name, set()) and _is_usable(r)
    ]
    if not relevant:
        return None

    worst_value: float | None = None
    worst_confidence: Confidence | None = None
    for tool_result in relevant:
        items = _extract_items(tool_result)
        for item in items:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.LOW,
                    description=item["description"],
                    file=item.get("file"),
                    line=item.get("line"),
                    confidence=_confidence_for_tool(tool_result.tool_name),
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
        value = _band_value(len(items))
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


def _extract_items(tool_result: ToolResult) -> list[dict[str, Any]]:
    if tool_result.tool_name == "vulture":
        return [
            {
                "description": f"unused {f['kind']} '{f['name']}'",
                "file": f.get("file"),
                "line": f.get("line"),
            }
            for f in tool_result.raw_output.get("findings", [])
        ]
    if tool_result.tool_name == "knip":
        return _extract_knip_items(tool_result.raw_output["issues"])
    return [
        {
            "description": f"{v.get('rule', 'unused code')}: {v.get('message', '')}",
            "file": v.get("file"),
            "line": v.get("line"),
        }
        for v in tool_result.raw_output.get("violations", [])
        if v.get("ruleset") == "unusedcode"
    ]


def _extract_knip_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten knip 6.x per-file issue rows into dead-code items.

    Each row carries its own `files` (the row's file is fully unused), plus
    `exports`/`types`/`enumMembers` lists of objects. `duplicates` is a list
    of groups, each group a list of objects, and counts as one item per group.
    """
    items: list[dict[str, Any]] = []
    for issue in issues:
        file_name = issue.get("file")
        items.extend(
            {"description": f"unused file '{entry.get('name')}'", "file": entry.get("name")}
            for entry in issue.get("files", [])
        )
        for category in _KNIP_UNUSED_SYMBOL_CATEGORIES:
            category_name = category[:-1] if category.endswith("s") else category
            items.extend(
                {
                    "description": f"unused {category_name} '{entry.get('name')}'",
                    "file": file_name,
                    "line": entry.get("line"),
                }
                for entry in issue.get(category, [])
            )
        for group in issue.get("duplicates", []):
            if not group:
                continue
            names = ", ".join(f"'{entry.get('name')}'" for entry in group)
            items.append(
                {
                    "description": f"duplicate exports {names}",
                    "file": file_name,
                    "line": group[0].get("line"),
                }
            )
    return items


def _is_usable(tool_result: ToolResult) -> bool:
    """Tell whether a tool result carries real data rather than a fallback payload.

    Knip's runner falls back to `{"stdout", "stderr"}` when npx fails, output
    is unparsable, or no entry point exists; that must not score as clean.
    """
    if tool_result.tool_name == "knip":
        return "issues" in tool_result.raw_output
    return True


def _band_value(item_count: int) -> float:
    for max_count, value in _BANDS:
        if item_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _confidence_for_tool(tool_name: str) -> Confidence:
    return Confidence.HIGH if tool_name == "knip" else Confidence.MEDIUM
