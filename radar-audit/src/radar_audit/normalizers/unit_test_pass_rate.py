from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# pytest-cov's exit code 5 ("no tests collected") is still a usable, successful run --
# its tests.total is naturally 0 and contributes nothing to the summed ratio. exit 127
# (binary/tool missing) is excluded from all three.
_USABLE_EXIT_CODES_BY_TOOL = {
    "pytest-cov": {0, 1, 5},
    "vitest": {0, 1},
    "pest": {0, 1},
}
_RELEVANT_TOOLS = set(_USABLE_EXIT_CODES_BY_TOOL)
# Fixed floor (not a scored band) per spec §3.1's design decision to keep coverage
# out of the score arithmetic entirely -- informational only.
_COVERAGE_FLOOR = 50.0


def normalize_unit_test_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = []
    for r in tool_results:
        if r.tool_name not in _RELEVANT_TOOLS:
            continue
        if r.exit_code in _USABLE_EXIT_CODES_BY_TOOL[r.tool_name]:
            relevant.append(r)
        elif r.raw_output.get("tests", {}).get("total", 0) > 0:
            # Crashed or interrupted run (e.g. pytest exit code 2 from
            # collection errors) whose junit.xml still carries real counts -
            # rescue it into the ratio instead of silently dropping the
            # whole suite. The abnormal exit code itself is flagged below.
            relevant.append(r)
    if not relevant:
        return None

    passed = 0
    collected = 0
    for tool_result in relevant:
        tests = tool_result.raw_output.get("tests", {})
        passed += tests.get("passed", 0)
        collected += tests.get("total", 0)

        if tool_result.exit_code not in _USABLE_EXIT_CODES_BY_TOOL[tool_result.tool_name]:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.HIGH,
                    description=(
                        f"{tool_result.tool_name} exited abnormally (exit code "
                        f"{tool_result.exit_code}) while still reporting "
                        f"{tests.get('total', 0)} tests "
                        f"({tests.get('passed', 0)} passed) - treating as a crashed run"
                    ),
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

        for failure in tool_result.raw_output.get("failures", []):
            _add_failure_finding(session, scoring_run, criterion, tool_result, failure)

        coverage_percent = tool_result.raw_output.get("coverage_percent")
        if coverage_percent is not None and coverage_percent < _COVERAGE_FLOOR:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.LOW,
                    description=(
                        f"Coverage is {coverage_percent}%, below the {_COVERAGE_FLOOR}% floor"
                    ),
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

    if collected == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(passed / collected) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _add_failure_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    failure: dict[str, object],
) -> None:
    name = failure.get("name") or "unknown test"
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=f"Failing test: {name}",
            file=failure.get("file"),
            line=failure.get("line"),
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
