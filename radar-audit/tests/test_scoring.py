import pytest
from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.shared import get_criterion
from radar_audit.orchestrator import execute_audit
from radar_audit.scoring import (
    NoAuditFoundError,
    RepositoryNotFoundError,
    score_repository,
)
from radar_core.enums import ScoreLevel
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score
from sqlmodel import select

from tests.git_helpers import init_git_repo


def _audited_repo(db_session, tmp_path, name="repo", files=None):
    repo_path = tmp_path / name
    init_git_repo(repo_path, files=files or {})
    config = PortfolioConfig(repos_root=tmp_path, repositories=[name])
    return execute_audit(db_session, config, name, DEFAULT_RUNNERS)


def test_score_repository_raises_when_repository_unknown(db_session):
    with pytest.raises(RepositoryNotFoundError, match="does-not-exist"):
        score_repository(db_session, "does-not-exist")


def test_score_repository_raises_when_no_audit_exists(db_session):
    from radar_core.models.repository import Repository

    db_session.add(Repository(name="unaudited", path="/tmp/unaudited"))
    db_session.commit()

    with pytest.raises(NoAuditFoundError, match="unaudited"):
        score_repository(db_session, "unaudited")


def test_score_repository_creates_criterion_and_category_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    criterion_scores = [s for s in scores if s.level == ScoreLevel.CRITERION]
    category_scores = [s for s in scores if s.level == ScoreLevel.CATEGORY]

    assert len(criterion_scores) >= 1
    assert len(category_scores) >= 1
    assert all(0.0 <= s.value <= 10.0 for s in category_scores)


def test_score_repository_is_idempotent_no_duplicate_scores(db_session, tmp_path):
    _audited_repo(
        db_session,
        tmp_path,
        files={"DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n"},
    )

    first_run = score_repository(db_session, "repo")
    first_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == first_run.id)).all()
    )

    second_run = score_repository(db_session, "repo")
    second_count = len(
        db_session.exec(select(Score).where(Score.scoring_run_id == second_run.id)).all()
    )

    assert first_run.id == second_run.id
    assert first_count == second_count


def test_category_score_redistributes_weight_over_scored_criteria_only(db_session, tmp_path):
    # Architecture & design has 4 criteria at weight 25.0 each, but only 3 are
    # ever scored (1.4 has no normalizer). Equal weights mean the redistributed
    # weighted average reduces to a plain average of exactly those 3 -- not a
    # naive /4 average that would silently treat the missing one as a zero.
    _audited_repo(
        db_session,
        tmp_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )

    scoring_run = score_repository(db_session, "repo")
    methodology_version_id = scoring_run.methodology_version_id
    arch_criterion = get_criterion(
        db_session,
        methodology_version_id,
        "Architecture & design",
        "Dependency direction / circularity",
    )
    arch_criterion_ids = {
        c.id
        for c in db_session.exec(
            select(Criterion).where(Criterion.category_id == arch_criterion.category_id)
        ).all()
    }

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    arch_criterion_scores = [
        s
        for s in scores
        if s.level == ScoreLevel.CRITERION and s.criterion_id in arch_criterion_ids
    ]
    arch_category_score = next(
        s
        for s in scores
        if s.level == ScoreLevel.CATEGORY and s.category_id == arch_criterion.category_id
    )

    assert len(arch_criterion_scores) == 3
    expected = sum(s.value for s in arch_criterion_scores) / len(arch_criterion_scores)
    assert arch_category_score.value == pytest.approx(expected)
