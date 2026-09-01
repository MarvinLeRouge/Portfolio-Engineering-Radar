import json

from radar_audit.runners.precommit_gate_runner import PreCommitGateRunner

from tests.git_helpers import init_git_repo

_PRECOMMIT_CONFIG = """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v9.0.0
    hooks:
      - id: eslint
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.0.0
    hooks:
      - id: prettier
  - repo: local
    hooks:
      - id: vue-tsc
        name: vue-tsc
        entry: vue-tsc --noEmit
        language: system
"""

_LEFTHOOK_CONFIG = """
pre-commit:
  commands:
    lint:
      run: eslint .
    format:
      run: prettier --check .
"""


def test_reports_none_tier_when_no_hook_config_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"tier": "none", "entries": []}


def test_parses_precommit_config_hooks(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".pre-commit-config.yaml": _PRECOMMIT_CONFIG})

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "pre-commit"
    ids = [e["id"] for e in result.raw_output["entries"]]
    assert ids == ["ruff", "ruff-format", "mypy", "eslint", "prettier", "vue-tsc"]
    assert all(e["files"] is None for e in result.raw_output["entries"])


def test_chains_husky_hook_through_lint_staged_with_directory_scoped_patterns(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            ".husky/pre-commit": (
                '#!/usr/bin/env sh\n. "$(dirname "$0")/_/husky.sh"\n\nnpx lint-staged\n'
            ),
            "package.json": json.dumps(
                {
                    "lint-staged": {
                        "backend/**/*.js": "eslint --fix",
                        "frontend/**/*.js": "eslint --fix",
                    }
                }
            ),
        },
    )

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "husky"
    assert result.raw_output["entries"] == [
        {"id": "eslint", "files": "backend/**/*.js"},
        {"id": "eslint", "files": "frontend/**/*.js"},
    ]


def test_husky_hook_not_delegating_to_lint_staged_reports_empty_entries(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".husky/pre-commit": "#!/usr/bin/env sh\nnpm test\n"})

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output == {"tier": "husky", "entries": []}


def test_parses_lefthook_config_commands(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"lefthook.yml": _LEFTHOOK_CONFIG})

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "lefthook"
    assert result.raw_output["entries"] == [
        {"id": "eslint", "files": None},
        {"id": "prettier", "files": None},
    ]


def test_precommit_config_takes_priority_over_husky_and_lefthook(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            ".pre-commit-config.yaml": _PRECOMMIT_CONFIG,
            ".husky/pre-commit": "npx lint-staged\n",
            "lefthook.yml": _LEFTHOOK_CONFIG,
        },
    )

    runner = PreCommitGateRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["tier"] == "pre-commit"


def test_reports_tool_identity():
    runner = PreCommitGateRunner()

    assert runner.tool_name == "pre-commit-gate"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
