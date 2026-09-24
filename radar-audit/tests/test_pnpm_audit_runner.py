import json
import subprocess

from radar_audit.runners.pnpm_audit_runner import PnpmAuditRunner

from tests.git_helpers import init_git_repo


def _pnpm_install(repo_path):
    subprocess.run(["pnpm", "install", "--no-frozen-lockfile"], cwd=repo_path, check=True)


def _npm_install(repo_path):
    subprocess.run(["npm", "install", "--package-lock-only"], cwd=repo_path, check=True)


def _yarn_install(repo_path):
    subprocess.run(["npx", "--package=yarn", "--", "yarn", "install"], cwd=repo_path, check=True)


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


def test_dispatches_to_npm_audit_when_package_lock_json_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps(
                {"name": "npm-dispatch-test", "dependencies": {"lodash": "4.17.15"}}
            )
        },
    )
    _npm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.command.startswith("npm audit")
    assert result.raw_output["manifest_found"] is True
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert len(vulnerabilities) > 0
    assert all(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_prefers_npm_lockfile_when_multiple_lockfiles_are_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": json.dumps({"name": "multi-lock-test", "dependencies": {}})},
    )
    _npm_install(repo_path)
    (repo_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.command.startswith("npm audit")


def test_reports_a_failed_audit_when_no_supported_lockfile_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": json.dumps({"name": "no-lock-test", "dependencies": {}})},
    )

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["error"]["code"] == "NO_LOCKFILE_DETECTED"
    assert "vulnerabilities" not in result.raw_output


def test_npm_parser_skips_transitive_via_string_entries():
    stdout = json.dumps(
        {
            "vulnerabilities": {
                "lodash": {
                    "via": [{"source": 1106913, "name": "lodash", "severity": "high"}],
                    "fixAvailable": {"name": "lodash", "version": "4.18.1"},
                },
                "some-wrapper": {
                    "via": ["lodash"],
                    "fixAvailable": False,
                },
            }
        }
    )

    vulnerabilities = PnpmAuditRunner._parse_npm_audit(stdout)

    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]["package"] == "lodash"
    assert vulnerabilities[0]["id"] == "1106913"
    assert vulnerabilities[0]["severity"] == "HIGH"


def test_npm_parser_reports_no_fix_available_when_fixavailable_is_false():
    stdout = json.dumps(
        {
            "vulnerabilities": {
                "lodash": {
                    "via": [{"source": 1106913, "name": "lodash", "severity": "high"}],
                    "fixAvailable": False,
                }
            }
        }
    )

    vulnerabilities = PnpmAuditRunner._parse_npm_audit(stdout)

    assert vulnerabilities[0]["fix_available"] is False


def test_dispatches_to_yarn_audit_when_yarn_lock_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps(
                {"name": "yarn-dispatch-test", "dependencies": {"lodash": "4.17.15"}}
            )
        },
    )
    _yarn_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert "yarn" in result.command
    assert result.raw_output["manifest_found"] is True
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert len(vulnerabilities) > 0
    assert all(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_yarn_parser_returns_none_when_no_summary_line_is_reached():
    stdout = '{"type":"warning","data":"something"}\n'

    result = PnpmAuditRunner._parse_yarn_audit(stdout)

    assert result is None


def test_reports_tool_identity():
    runner = PnpmAuditRunner()

    assert runner.tool_name == "pnpm-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
