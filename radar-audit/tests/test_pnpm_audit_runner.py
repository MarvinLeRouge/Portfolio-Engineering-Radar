import json
import subprocess

from radar_audit.runners.pnpm_audit_runner import PnpmAuditRunner

from tests.git_helpers import init_git_repo


def _pnpm_install(repo_path):
    subprocess.run(["pnpm", "install", "--no-frozen-lockfile"], cwd=repo_path, check=True)


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": "console.log('hi');\n"})

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_empty_dependencies(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": json.dumps({"name": "clean-test", "dependencies": {}})},
    )
    _pnpm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps({"name": "vuln-test", "dependencies": {"lodash": "4.17.15"}})
        },
    )
    _pnpm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_reports_tool_identity():
    runner = PnpmAuditRunner()

    assert runner.tool_name == "pnpm-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
