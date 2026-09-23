import json
import subprocess

from radar_audit.runners.composer_audit_runner import ComposerAuditRunner

from tests.git_helpers import init_git_repo


def _composer_install(repo_path):
    subprocess.run(
        ["composer", "install", "--no-interaction", "--quiet"], cwd=repo_path, check=True
    )


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.php": "<?php\n"})

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_a_clean_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps({"name": "test/clean-test", "require": {"psr/log": "^3.0"}})
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    # "audit.block-insecure: false" is required -- Composer 2.9+ refuses to *install*
    # a package with known advisories by default, confirmed empirically.
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {
                    "name": "test/vuln-test",
                    "require": {"phpmailer/phpmailer": "6.1.0"},
                    "config": {"audit": {"block-insecure": False}},
                }
            )
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "phpmailer/phpmailer" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_reports_a_failed_audit_when_dependencies_are_neither_locked_nor_installed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps({"name": "test/no-lock", "require": {"psr/log": "^3.0"}})
        },
    )

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert "error" in result.raw_output
    assert "vulnerabilities" not in result.raw_output


def test_audits_the_lockfile_when_vendor_is_not_installed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {
                    "name": "test/lock-only",
                    "require": {"phpmailer/phpmailer": "6.1.0"},
                    "config": {"audit": {"block-insecure": False}},
                }
            )
        },
    )
    subprocess.run(
        ["composer", "update", "--no-install", "--no-interaction", "--quiet"],
        cwd=repo_path,
        check=True,
    )
    assert not (repo_path / "vendor").exists()

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "phpmailer/phpmailer" for v in vulnerabilities)


def test_reports_no_vulnerabilities_when_only_platform_requirements_are_declared(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"composer.json": json.dumps({"name": "test/platform", "require": {"php": ">=8.1"}})},
    )

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output == {"manifest_found": True, "vulnerabilities": []}


def test_reports_tool_identity():
    runner = ComposerAuditRunner()

    assert runner.tool_name == "composer-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
