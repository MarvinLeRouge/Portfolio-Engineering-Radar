from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"dependency-cruiser", "pydeps"}
# Band thresholds per quality-framework.md§4.1, keyed on the number of distinct
# cycles detected: 0 cycles=10, 1-2 cycles=6, 3-5 cycles=4, >5 cycles=2.
_BANDS: tuple[tuple[int, float], ...] = ((0, 10.0), (2, 6.0), (5, 4.0))
_ABOVE_HIGHEST_BAND_VALUE = 2.0


def _is_usable(tool_result: ToolResult) -> bool:
    """A 0-exit-code result that analyzed nothing must not be scored as "no
    cycles found" (the top band) -- that would be worse than a missing-data
    skip. dependency-cruiser signals "nothing analyzed" with an empty
    modules list; pydeps signals it when not a single module in its output
    declares any outbound import at all (its typical failure mode for
    src-layout or non-importable package roots).
    """
    if tool_result.tool_name == "dependency-cruiser":
        return bool(tool_result.raw_output.get("modules", []))
    imports_lists = (
        data.get("imports", [])
        for data in tool_result.raw_output.values()
        if isinstance(data, dict)
    )
    return any(imports_lists)


def normalize_dependency_circularity(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name in _RELEVANT_TOOLS and r.exit_code == 0]
    if not relevant:
        return None

    worst_value: float | None = None
    for tool_result in relevant:
        if not _is_usable(tool_result):
            continue
        cycles = _detect_cycles(tool_result)
        for cycle_nodes in cycles:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.MEDIUM,
                    description=f"Circular dependency involving: {', '.join(sorted(cycle_nodes))}",
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
        value = _band_value(len(cycles))
        if worst_value is None or value < worst_value:
            worst_value = value

    if worst_value is None:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=worst_value,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _band_value(cycle_count: int) -> float:
    for max_count, value in _BANDS:
        if cycle_count <= max_count:
            return value
    return _ABOVE_HIGHEST_BAND_VALUE


def _detect_cycles(tool_result: ToolResult) -> list[frozenset[str]]:
    if tool_result.tool_name == "dependency-cruiser":
        return _detect_cycles_dependency_cruiser(tool_result.raw_output)
    return _detect_cycles_pydeps(tool_result.raw_output)


def _detect_cycles_dependency_cruiser(raw_output: dict[str, object]) -> list[frozenset[str]]:
    modules = raw_output.get("modules", [])
    adjacency: dict[str, list[str]] = {}
    for module in modules:  # type: ignore[attr-defined]
        source = module["source"]
        for dependency in module.get("dependencies", []):
            if dependency.get("circular"):
                adjacency.setdefault(source, []).append(dependency["resolved"])
    return _detect_cycles_via_dfs(adjacency)


def _detect_cycles_pydeps(raw_output: dict[str, object]) -> list[frozenset[str]]:
    adjacency = {
        name: data.get("imports", []) for name, data in raw_output.items() if isinstance(data, dict)
    }
    return _detect_cycles_via_dfs(adjacency)


def _detect_cycles_via_dfs(adjacency: dict[str, list[str]]) -> list[frozenset[str]]:
    visited: set[str] = set()
    in_stack: set[str] = set()
    found: set[frozenset[str]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in in_stack:
            cycle_start = path.index(node)
            found.add(frozenset(path[cycle_start:]))
            return
        if node in visited or node not in adjacency:
            return
        visited.add(node)
        in_stack.add(node)
        for neighbor in adjacency.get(node, []):
            visit(neighbor, path + [node])
        in_stack.discard(node)

    for module_name in adjacency:
        if module_name not in visited:
            visit(module_name, [])

    return list(found)
