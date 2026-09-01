import subprocess

import pytest
from radar_audit.runners.phpstan_runner import PhpstanRunner

from tests.git_helpers import init_git_repo


def _init_composer_project(repo_path):
    (repo_path / "composer.json").write_text('{"name": "fixture/fixture"}\n')
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_no_errors_on_well_typed_php(tmp_path):
    repo_path = tmp_path / "repo"
    php_source = (
        "<?php\n\nclass A\n{\n"
        "    public function add(int $a, int $b): int\n"
        "    {\n        return $a + $b;\n    }\n}\n"
    )
    init_git_repo(repo_path, files={"src/A.php": php_source})
    _init_composer_project(repo_path)

    runner = PhpstanRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["totals"]["errors"] == 0


@pytest.mark.slow
def test_reverts_composer_json_and_lock_byte_identical(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A\n{\n}\n"})
    _init_composer_project(repo_path)
    original_json = (repo_path / "composer.json").read_bytes()
    original_lock = (repo_path / "composer.lock").read_bytes()

    runner = PhpstanRunner()
    runner.run(repo_path, exclude_paths=[])

    assert (repo_path / "composer.json").read_bytes() == original_json
    assert (repo_path / "composer.lock").read_bytes() == original_lock


def test_reports_tool_identity():
    runner = PhpstanRunner()

    assert runner.tool_name == "phpstan"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


def test_build_neon_content_always_excludes_target_vendor(tmp_path):
    runner = PhpstanRunner()

    neon = runner._build_neon_content(is_laravel=False, target_path=tmp_path, exclude_paths=[])

    assert f"{tmp_path}/vendor/*" in neon


def test_build_neon_content_includes_caller_exclude_paths(tmp_path):
    runner = PhpstanRunner()
    excluded_dir = tmp_path / "some" / "excluded" / "dir"

    neon = runner._build_neon_content(
        is_laravel=False, target_path=tmp_path, exclude_paths=[excluded_dir]
    )

    assert f"{excluded_dir}/*" in neon
    assert f"{tmp_path}/vendor/*" in neon


def test_build_neon_content_includes_block_only_when_laravel(tmp_path):
    runner = PhpstanRunner()

    laravel_neon = runner._build_neon_content(
        is_laravel=True, target_path=tmp_path, exclude_paths=[]
    )
    bare_neon = runner._build_neon_content(is_laravel=False, target_path=tmp_path, exclude_paths=[])

    assert "includes:" in laravel_neon
    assert "vendor/larastan/larastan/extension.neon" in laravel_neon
    assert "includes:" not in bare_neon
