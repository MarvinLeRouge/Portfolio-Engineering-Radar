from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"ruff-check", "eslint", "pint"}
_USABLE_EXIT_CODES = {0, 1}


def normalize_lint_pass_rate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name in _RELEVANT_TOOLS and r.exit_code in _USABLE_EXIT_CODES
    ]
    if not relevant:
        return None

    covered = 0
    applicable = 0
    for tool_result in relevant:
        file_covered, file_applicable = _score_files(session, scoring_run, criterion, tool_result)
        covered += file_covered
        applicable += file_applicable

    if applicable == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(covered / applicable) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _score_files(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    if tool_result.tool_name == "ruff-check":
        return _score_ruff(session, scoring_run, criterion, tool_result)
    if tool_result.tool_name == "eslint":
        return _score_eslint(session, scoring_run, criterion, tool_result)
    return _score_pint(session, scoring_run, criterion, tool_result)


def _score_ruff(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    applicable = tool_result.raw_output.get("total_files", 0)
    violations = tool_result.raw_output.get("violations", [])
    flagged_files = {v["filename"] for v in violations}
    for violation in violations:
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            f"{violation['code']}: {violation['message']}",
            file=violation["filename"],
            line=violation["location"]["row"],
        )
    return applicable - len(flagged_files), applicable


def _score_eslint(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    results = tool_result.raw_output.get("results", [])
    applicable = len(results)
    covered = 0
    for entry in results:
        if entry["errorCount"] == 0:
            covered += 1
            continue
        for message in entry["messages"]:
            _add_finding(
                session,
                scoring_run,
                criterion,
                tool_result,
                f"{message.get('ruleId') or 'parse-error'}: {message['message']}",
                file=entry["filePath"],
                line=message.get("line"),
            )
    return covered, applicable


def _score_pint(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    if tool_result.raw_output.get("result") == "passed":
        return 1, 1  # single subproject-level pass/fail signal, no per-file breakdown available
    files = tool_result.raw_output.get("files", [])
    for entry in files:
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            "file does not conform to the project's Pint style",
            file=entry.get("path"),
        )
    return 0, 1


def _add_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    description: str,
    file: str | None = None,
    line: int | None = None,
) -> None:
    session.add(
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=description,
            file=file,
            line=line,
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
