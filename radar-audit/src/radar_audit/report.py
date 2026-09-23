from __future__ import annotations

from pathlib import Path

from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_audit.scoring import get_repository_by_name


class NoScoringRunFoundError(ValueError):
    """Raised when a Repository has no ScoringRun row yet."""


def _get_latest_scoring_run(
    session: Session, repository_id: int, repository_name: str
) -> ScoringRun:
    scoring_run = session.exec(
        select(ScoringRun)
        .join(Audit, Audit.id == ScoringRun.audit_id)  # type: ignore[arg-type]
        .where(Audit.repository_id == repository_id)
        .order_by(desc(ScoringRun.scored_at))  # type: ignore[arg-type]
    ).first()
    if scoring_run is None:
        msg = (
            f"No score found for {repository_name!r} -- run 'radar-audit score "
            f"{repository_name}' first"
        )
        raise NoScoringRunFoundError(msg)
    return scoring_run


def render_report(session: Session, repo_name: str) -> str:
    repository = get_repository_by_name(session, repo_name)
    assert repository.id is not None
    scoring_run = _get_latest_scoring_run(session, repository.id, repository.name)
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None

    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(Category.order)  # type: ignore[arg-type]
    ).all()

    scores = session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    category_scores = {s.category_id: s for s in scores if s.level == ScoreLevel.CATEGORY}
    criterion_scores = {s.criterion_id: s for s in scores if s.level == ScoreLevel.CRITERION}

    lines = [
        f"# Report: {repository.name}",
        "",
        f"- Commit: `{audit.commit_sha}`",
        f"- Audited at: {audit.audited_at.isoformat()}",
        f"- Scored at: {scoring_run.scored_at.isoformat()}",
        "",
    ]

    for category in categories:
        category_score = category_scores.get(category.id)

        if category_score is None:
            lines.append(f"## {category.order}. {category.name} -- Not yet audited")
            lines.append("")
            continue

        lines.append(
            f"## {category.order}. {category.name} -- {category_score.value:.1f}/10 "
            f"({category_score.confidence.value} confidence)"
        )
        criteria = session.exec(
            select(Criterion).where(Criterion.category_id == category.id).order_by(Criterion.id)  # type: ignore[arg-type]
        ).all()
        for criterion in criteria:
            criterion_score = criterion_scores.get(criterion.id)
            if criterion_score is None:
                lines.append(f"- {criterion.name}: not scored this run")
            else:
                lines.append(f"- {criterion.name}: {criterion_score.value:.1f}/10")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(markdown: str, repo_name: str, output_dir: Path) -> Path:
    target_dir = output_dir / repo_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "latest.md"
    target_path.write_text(markdown)
    return target_path
