from __future__ import annotations

from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.scoring import ScoringRun
from sqlmodel import Session, select


def get_or_create_scoring_run(
    session: Session, audit: Audit, methodology_version: MethodologyVersion
) -> ScoringRun:
    """Get or create the ScoringRun for this Audit + MethodologyVersion pair.

    Mirrors orchestrator.get_or_create_audit's reuse pattern, keyed on the model's
    (audit_id, methodology_version_id) unique constraint.
    """
    existing = session.exec(
        select(ScoringRun).where(
            ScoringRun.audit_id == audit.id,
            ScoringRun.methodology_version_id == methodology_version.id,
        )
    ).first()
    if existing is not None:
        return existing

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    session.add(scoring_run)
    session.commit()
    session.refresh(scoring_run)
    return scoring_run


class CriterionNotFoundError(ValueError):
    """Raised when a (category_name, criterion_name) pair isn't found in the seeded taxonomy."""


def get_criterion(
    session: Session,
    methodology_version_id: int,
    category_name: str,
    criterion_name: str,
) -> Criterion:
    """Look up a seeded Criterion by its category and criterion name, exactly as seeded from
    quality_framework_v1_0.yaml.
    """
    criterion = session.exec(
        select(Criterion)
        .join(Category, Category.id == Criterion.category_id)  # type: ignore[arg-type]
        .where(
            Category.methodology_version_id == methodology_version_id,
            Category.name == category_name,
            Criterion.name == criterion_name,
        )
    ).first()
    if criterion is None:
        raise CriterionNotFoundError(
            f"No criterion {criterion_name!r} in category {category_name!r} "
            f"for methodology_version_id={methodology_version_id}"
        )
    return criterion
