# src/radar_audit/normalizers/precommit_gate.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_VALIDATOR_TYPES = ("lint", "format", "type-check")

# Maps a sibling tool's tool_name to the domain its presence implies, mirroring the
# orchestrator's own python/php -> backend, javascript -> frontend mapping (spec §7).
# Used to determine which domains are actually present in the audited repo, since
# PreCommitGateRunner (scope="repo") has no direct subproject/stack info of its own.
_STACK_TOOL_NAMES: dict[str, str] = {
    "ruff-check": "backend",
    "mypy": "backend",
    "pint": "backend",
    "phpstan": "backend",
    "radon-cc": "backend",
    "phpmd-codesize": "backend",
    "eslint": "frontend",
    "tsc": "frontend",
    "eslint-complexity": "frontend",
}

# Recognized hook/command id -> (validator_type, default domain), per spec §7 points
# 1-2 (pre-commit's fixed lookup table, extended with pint/phpstan for husky's
# lint-staged chain per spec §3.1's PHP lint/type-check split). An id not present
# here contributes no matrix cell -- e.g. a custom local hook with no known tool.
_HOOK_ID_CLASSIFICATION: dict[str, tuple[str, str]] = {
    "ruff": ("lint", "backend"),
    "ruff-format": ("format", "backend"),
    "mypy": ("type-check", "backend"),
    "eslint": ("lint", "frontend"),
    "prettier": ("format", "frontend"),
    "vue-tsc": ("type-check", "frontend"),
    "tsc": ("type-check", "frontend"),
    "pint": ("lint", "backend"),
    "phpstan": ("type-check", "backend"),
}


def normalize_precommit_gate(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "pre-commit-gate" and r.exit_code == 0]
    if not relevant:
        return None

    domains = _domains_present(tool_results)
    if not domains:
        return None

    tool_result = relevant[0]
    tier = tool_result.raw_output.get("tier")
    entries = tool_result.raw_output.get("entries", [])

    # HIGH by default; LOW when the lefthook.yml detection path was used
    # (spec §7 point 3 -- lefthook is unverified against any real in-scope config).
    gate_confidence = Confidence.LOW if tier == "lefthook" else Confidence.HIGH

    cells: dict[tuple[str, str], bool] = {
        (validator_type, domain): False for domain in domains for validator_type in _VALIDATOR_TYPES
    }
    for entry in entries:
        classified = _classify_entry(entry)
        if classified is not None and classified in cells:
            cells[classified] = True

    applicable = len(cells)
    covered = sum(1 for is_covered in cells.values() if is_covered)
    if covered == applicable:
        value = 10.0
    elif covered == 0:
        value = 0.0
    else:
        value = (covered / applicable) * 10

    for (validator_type, domain), is_covered in cells.items():
        if not is_covered:
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.LOW,
                    description=f"No pre-commit {validator_type} hook covers {domain}",
                    confidence=gate_confidence,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=gate_confidence,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _domains_present(tool_results: list[ToolResult]) -> set[str]:
    return {
        _STACK_TOOL_NAMES[r.tool_name] for r in tool_results if r.tool_name in _STACK_TOOL_NAMES
    }


def _classify_entry(entry: dict[str, str | None]) -> tuple[str, str] | None:
    hook_id = entry.get("id")
    if not isinstance(hook_id, str):
        return None
    base = _HOOK_ID_CLASSIFICATION.get(hook_id)
    if base is None:
        return None
    validator_type, default_domain = base
    files = entry.get("files")
    if isinstance(files, str) and "backend" in files:
        domain = "backend"
    elif isinstance(files, str) and "frontend" in files:
        domain = "frontend"
    else:
        domain = default_domain
    return (validator_type, domain)
