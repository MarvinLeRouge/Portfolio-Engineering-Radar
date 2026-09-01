from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_TODO, _IN_PROGRESS, _DONE = 0, 1, 2
_VALUE_BY_STATUS = {_TODO: 0.0, _IN_PROGRESS: 5.0, _DONE: 10.0}


def normalize_e2e_tests(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    playwright_results = [
        r for r in tool_results if r.tool_name == "playwright-presence" and r.exit_code == 0
    ]
    if not playwright_results:
        # No javascript sub-project ran PlaywrightPresenceRunner at all -> N/A.
        return None

    ci_results = [r for r in tool_results if r.tool_name == "ci-workflow" and r.exit_code == 0]
    ci_wired = bool(
        ci_results and ci_results[0].raw_output.get("playwright_execution_found", False)
    )

    # Worst-status-wins across every javascript sub-project (spec section 7).
    worst_status = min(
        _status_for(bool(r.raw_output.get("present", False)), ci_wired) for r in playwright_results
    )

    if worst_status == _TODO:
        _add_finding(
            session,
            scoring_run,
            criterion,
            playwright_results[0],
            FindingSeverity.MEDIUM,
            "Repo is web-facing but has no Playwright E2E test setup",
        )
    elif worst_status == _IN_PROGRESS:
        _add_finding(
            session,
            scoring_run,
            criterion,
            playwright_results[0],
            FindingSeverity.LOW,
            "Playwright is present but not wired into any CI workflow",
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_VALUE_BY_STATUS[worst_status],
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _status_for(present: bool, ci_wired: bool) -> int:
    if not present:
        return _TODO
    return _DONE if ci_wired else _IN_PROGRESS


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    severity: FindingSeverity,
    description: str,
) -> None:
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=severity,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
