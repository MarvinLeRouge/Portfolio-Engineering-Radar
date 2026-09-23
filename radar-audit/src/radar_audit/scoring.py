from __future__ import annotations

from datetime import UTC, datetime

from radar_core.enums import Confidence, ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Category, Criterion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlalchemy import desc
from sqlmodel import Session, select

from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


class RepositoryNotFoundError(ValueError):
    """Raised when no Repository row exists for the given name."""


class NoAuditFoundError(ValueError):
    """Raised when a Repository has no Audit row yet."""


def get_repository_by_name(session: Session, repo_name: str) -> Repository:
    repository = session.exec(select(Repository).where(Repository.name == repo_name)).first()
    if repository is None:
        raise RepositoryNotFoundError(
            f"No repository named {repo_name!r} -- run 'radar-audit run {repo_name}' first"
        )
    return repository


def _get_latest_audit(session: Session, repository: Repository) -> Audit:
    audit = session.exec(
        select(Audit).where(Audit.repository_id == repository.id).order_by(desc(Audit.audited_at))  # type: ignore[arg-type]
    ).first()
    if audit is None:
        raise NoAuditFoundError(
            f"No audit found for {repository.name!r} -- run 'radar-audit run "
            f"{repository.name}' first"
        )
    return audit


def score_repository(session: Session, repo_name: str) -> ScoringRun:
    repository = get_repository_by_name(session, repo_name)
    audit = _get_latest_audit(session, repository)
    methodology_version = seed_taxonomy(session)
    scoring_run = get_or_create_scoring_run(session, audit, methodology_version)

    existing_scores = session.exec(
        select(Score).where(Score.scoring_run_id == scoring_run.id)
    ).all()
    for existing in existing_scores:
        session.delete(existing)

    existing_findings = session.exec(
        select(Finding).where(Finding.scoring_run_id == scoring_run.id)
    ).all()
    for existing_finding in existing_findings:
        session.delete(existing_finding)

    scoring_run.scored_at = datetime.now(UTC)
    session.add(scoring_run)
    session.commit()

    tool_results = list(session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)))

    methodology_version_id = methodology_version.id
    assert methodology_version_id is not None

    scored_by_category: dict[int, list[tuple[Criterion, Score]]] = {}
    for (category_name, criterion_name), normalizer in CRITERION_NORMALIZERS.items():
        criterion = get_criterion(session, methodology_version_id, category_name, criterion_name)
        score = normalizer(session, scoring_run, criterion, tool_results)
        if score is None:
            continue
        scored_by_category.setdefault(criterion.category_id, []).append((criterion, score))

    for category_id, pairs in scored_by_category.items():
        category = session.get(Category, category_id)
        assert category is not None
        _write_category_score(session, scoring_run, category, pairs)

    return scoring_run


def _write_category_score(
    session: Session,
    scoring_run: ScoringRun,
    category: Category,
    pairs: list[tuple[Criterion, Score]],
) -> Score:
    total_weight = sum(criterion.weight for criterion, _ in pairs)
    weighted_sum = sum(criterion.weight * score.value for criterion, score in pairs)
    value = weighted_sum / total_weight
    confidence = max((score.confidence for _, score in pairs), key=lambda c: _CONFIDENCE_RANK[c])

    category_score = Score(
        scoring_run_id=scoring_run.id,
        category_id=category.id,
        level=ScoreLevel.CATEGORY,
        value=value,
        confidence=confidence,
    )
    session.add(category_score)
    session.commit()
    session.refresh(category_score)
    return category_score
