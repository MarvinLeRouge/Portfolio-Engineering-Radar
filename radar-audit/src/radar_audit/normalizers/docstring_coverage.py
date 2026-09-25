from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_DOCVET_USABLE_EXIT_CODES = {0}
_PHPDOC_CHECKER_USABLE_EXIT_CODES = {0, 1}
_PHP_UNDOCUMENTED_TYPES = {"class", "method"}
_PHP_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (5, 8.0), (15, 6.0), (30, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def normalize_docstring_coverage(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    worst_value: float | None = None
    worst_confidence: Confidence | None = None

    for tool_result in tool_results:
        if tool_result.tool_name == "docvet" and tool_result.exit_code in _DOCVET_USABLE_EXIT_CODES:
            value = _score_docvet(session, scoring_run, criterion, tool_result)
        elif (
            tool_result.tool_name == "phpdoc-checker"
            and tool_result.exit_code in _PHPDOC_CHECKER_USABLE_EXIT_CODES
        ):
            value = _score_phpdoc_checker(session, scoring_run, criterion, tool_result)
        else:
            continue

        if value is None:
            continue
        if worst_value is None or value < worst_value:
            worst_value = value
            worst_confidence = Confidence.MEDIUM

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


def _score_docvet(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> float | None:
    presence_coverage = tool_result.raw_output.get("presence_coverage")
    if not presence_coverage:
        return None

    for finding in tool_result.raw_output.get("findings", []):
        rule = finding.get("rule", "missing-docstring")
        message = finding.get("message", "")
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=f"{rule}: {message}",
                file=finding.get("file"),
                line=finding.get("line"),
                confidence=Confidence.MEDIUM,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    percentage: float = presence_coverage["percentage"]
    return percentage / 10


def _score_phpdoc_checker(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> float | None:
    findings = tool_result.raw_output.get("findings")
    if findings is None:
        return None

    errors_count = 0
    for finding in findings:
        if finding.get("type") not in _PHP_UNDOCUMENTED_TYPES:
            continue
        errors_count += 1
        method_suffix = f"::{finding['method']}" if finding.get("method") else ""
        session.add(
            Finding(
                scoring_run_id=scoring_run.id,
                criterion_id=criterion.id,
                tool_result_id=tool_result.id,
                severity=FindingSeverity.LOW,
                description=(
                    f"{finding['type']} '{finding.get('class', '')}{method_suffix}' has no docblock"
                ),
                file=finding.get("file"),
                line=finding.get("line"),
                confidence=Confidence.MEDIUM,
                status=FindingStatus.OPEN,
                human_verdict=HumanVerdict.UNREVIEWED,
            )
        )

    return _band_value(errors_count)


def _band_value(errors_count: int) -> float:
    for max_count, value in _PHP_BANDS:
        if errors_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE
