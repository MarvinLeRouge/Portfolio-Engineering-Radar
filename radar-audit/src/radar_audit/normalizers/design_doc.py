from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Provisional threshold, not yet calibrated against the real portfolio (see spec §7/§9).
_NON_TRIVIAL_LINE_THRESHOLD = 30


def normalize_design_doc(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r for r in tool_results if r.tool_name == "design-doc-presence" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    found_path = tool_result.raw_output.get("found_path")
    non_blank_lines = tool_result.raw_output.get("non_blank_lines", 0)

    if found_path is None:
        value = 0.0
        _add_finding(
            session, scoring_run, criterion, tool_result, "no architectural documentation found"
        )
    elif non_blank_lines >= _NON_TRIVIAL_LINE_THRESHOLD:
        value = 10.0
    else:
        value = 6.0
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            f"architectural documentation at {found_path} is trivial "
            f"({non_blank_lines} non-blank lines)",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    description: str,
) -> None:
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
