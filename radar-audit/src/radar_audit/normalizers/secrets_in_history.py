from __future__ import annotations

import re
from typing import Any

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.shared import has_success_payload

# Pre-filter rules per quality-framework.md§3.2 (Phase 3 pilot calibration): a
# generic-api-key hit in a tests?/ path on a fake_*/mock_*/dummy_* variable, or a
# hit whose file matches .env.*.example/.template/.sample, is a probable false
# positive -- held at low confidence rather than counted as "confirmed" (the P1
# critical penalty itself is out of scope for this increment, see the spec).
_TEST_PATH_RE = re.compile(r"(^|/)tests?(/|$)")
_TEST_VAR_RE = re.compile(r"\b(fake|mock|dummy)_\w*", re.IGNORECASE)
_ENV_EXAMPLE_RE = re.compile(r"\.env\.[^/]*\.(example|template|sample)$")


def _is_pre_filtered(finding: dict[str, Any]) -> bool:
    if finding["rule"] == "generic-api-key":
        if _TEST_PATH_RE.search(finding["file"]) and _TEST_VAR_RE.search(finding["match"]):
            return True
    return bool(_ENV_EXAMPLE_RE.search(finding["file"]))


def normalize_secrets_in_history(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    # A failed gitleaks run (crash record, Docker unreachable, missing report) is
    # missing data, never a clean "no secrets" result.
    relevant = [
        r for r in tool_results if r.tool_name == "gitleaks" and has_success_payload(r, "findings")
    ]
    if not relevant:
        return None

    any_confirmed = False
    any_pre_filtered = False
    for tool_result in relevant:
        for finding in tool_result.raw_output["findings"]:
            pre_filtered = _is_pre_filtered(finding)
            if pre_filtered:
                any_pre_filtered = True
            else:
                any_confirmed = True
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.HIGH,
                    description=f"{finding['rule']}: potential secret in {finding['file']}",
                    file=finding["file"],
                    line=finding["line"],
                    confidence=Confidence.LOW if pre_filtered else Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

    # Severity bands per the category-4 spec's section 3.2 - resolved but provisional,
    # pending Phase 5 portfolio-wide calibration: confirmed finding scores 2.0, pre-filtered
    # finding scores 8.0, no findings score 10.0.
    if any_confirmed:
        value = 2.0
    elif any_pre_filtered:
        value = 8.0
    else:
        value = 10.0

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
