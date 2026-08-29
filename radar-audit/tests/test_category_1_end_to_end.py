from radar_audit.cli import DEFAULT_RUNNERS
from radar_audit.config import PortfolioConfig
from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.module_size import normalize_module_size
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.orchestrator import execute_audit
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.scoring import Score
from sqlmodel import select

from tests.git_helpers import init_git_repo


def test_full_pipeline_from_audit_to_criterion_scores(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "mypkg/pyproject.toml": "[project]\nname='x'\n",
            "mypkg/__init__.py": "",
            "mypkg/a.py": "from mypkg import b\n",
            "mypkg/b.py": "x = 1\n",
            "DESIGN.md": "\n".join(f"line {i}" for i in range(40)) + "\n",
        },
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])

    audit = execute_audit(db_session, config, "repo", DEFAULT_RUNNERS)

    tool_results = db_session.exec(select(ToolResult).where(ToolResult.audit_id == audit.id)).all()
    assert {r.tool_name for r in tool_results} >= {"design-doc-presence", "pydeps", "radon-raw"}

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)

    circularity_criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Dependency direction / circularity",
    )
    doc_criterion = get_criterion(
        db_session,
        methodology_version.id,
        "Architecture & design",
        "Architectural documentation present",
    )
    size_criterion = get_criterion(
        db_session, methodology_version.id, "Architecture & design", "Module size distribution"
    )

    normalize_dependency_circularity(db_session, scoring_run, circularity_criterion, tool_results)
    normalize_design_doc(db_session, scoring_run, doc_criterion, tool_results)
    normalize_module_size(db_session, scoring_run, size_criterion, tool_results)

    scores = db_session.exec(select(Score).where(Score.scoring_run_id == scoring_run.id)).all()
    assert len(scores) == 3
    assert all(s.level == ScoreLevel.CRITERION for s in scores)

    doc_score = next(s for s in scores if s.criterion_id == doc_criterion.id)
    assert doc_score.value == 10.0  # DESIGN.md has 40 non-blank lines, above the 30-line threshold
