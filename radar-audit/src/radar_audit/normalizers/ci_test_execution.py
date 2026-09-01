from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_ci_test_execution(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "ci-workflow" and r.exit_code == 0]
    if not relevant:
        return None

    tool_result = relevant[0]
    test_execution_found = bool(tool_result.raw_output.get("test_execution_found", False))

    if not test_execution_found:
        # Total absence of CI test execution is always a real gap (never N/A) --
        # unlike 3.3, nothing structurally prevents any repo from having CI.
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.MEDIUM,
                description="No CI workflow invokes any test command",
                confidence=Confidence.HIGH,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=10.0 if test_execution_found else 0.0,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
