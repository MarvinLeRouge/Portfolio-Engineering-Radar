from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"radon-raw", "static-loc-count"}
# Provisional threshold, not yet calibrated against the real portfolio (see spec §7/§9).
_COVERED_LOC_THRESHOLD = 400


def normalize_module_size(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name in _RELEVANT_TOOLS and r.exit_code == 0]
    if not relevant:
        return None

    covered = 0
    applicable = 0
    for tool_result in relevant:
        for file_path, loc in _per_file_loc(tool_result).items():
            applicable += 1
            if loc <= _COVERED_LOC_THRESHOLD:
                covered += 1
            else:
                session.add(
                    Finding(
                        scoring_run_id=scoring_run.id,
                        criterion_id=criterion.id,
                        tool_result_id=tool_result.id,
                        severity=FindingSeverity.LOW,
                        description=(
                            f"{file_path} is {loc} non-blank lines, over the "
                            f"{_COVERED_LOC_THRESHOLD}-line threshold"
                        ),
                        file=file_path,
                        confidence=Confidence.MEDIUM,
                        status=FindingStatus.OPEN,
                        human_verdict=HumanVerdict.UNREVIEWED,
                    )
                )

    if applicable == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(covered / applicable) * 10,
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _per_file_loc(tool_result: ToolResult) -> dict[str, int]:
    if tool_result.tool_name == "radon-raw":
        return {
            path: data["sloc"]
            for path, data in tool_result.raw_output.items()
            if isinstance(data, dict) and "sloc" in data
        }
    return dict(tool_result.raw_output.get("files", {}))
