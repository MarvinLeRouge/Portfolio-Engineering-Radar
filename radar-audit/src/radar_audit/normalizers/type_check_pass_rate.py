from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"mypy", "tsc", "phpstan"}
_USABLE_EXIT_CODES = {0, 1}
_SOURCE_EXTENSIONS_BY_TOOL = {"mypy": "total_files", "tsc": "total_files"}


def normalize_type_check_pass_rate(
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
    if tool_result.tool_name == "phpstan":
        return _score_phpstan(session, scoring_run, criterion, tool_result)
    return _score_diagnostics_tool(session, scoring_run, criterion, tool_result)


def _score_diagnostics_tool(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    applicable = tool_result.raw_output.get("total_files", 0)
    diagnostics = tool_result.raw_output.get("diagnostics", [])
    flagged_files = {d["file"] for d in diagnostics}
    for diagnostic in diagnostics:
        _add_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            f"{diagnostic.get('code', 'type-error')}: {diagnostic['message']}",
            file=diagnostic["file"],
            line=diagnostic.get("line"),
        )
    return applicable - len(flagged_files), applicable


def _score_phpstan(
    session: Session, scoring_run: ScoringRun, criterion: Criterion, tool_result: ToolResult
) -> tuple[int, int]:
    files_with_errors = tool_result.raw_output.get("files", {})
    total_errors = tool_result.raw_output.get("totals", {}).get("file_errors", 0)
    for file_path, entry in files_with_errors.items():
        for message in entry.get("messages", []):
            _add_finding(
                session,
                scoring_run,
                criterion,
                tool_result,
                message["message"],
                file=file_path,
                line=message.get("line"),
            )
    # PHPStan's JSON only lists files WITH errors; the clean-file count isn't
    # directly available, so treat "no errors" as the applicable=covered=1 signal
    # and each errored file as one uncovered unit against the same denominator.
    if total_errors == 0:
        return 1, 1
    return 0, len(files_with_errors) or 1


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
            severity=FindingSeverity.MEDIUM,
            description=description,
            file=file,
            line=line,
            confidence=Confidence.HIGH,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        )
    )
