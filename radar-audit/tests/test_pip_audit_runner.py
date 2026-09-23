from radar_audit.runners.pip_audit_runner import PipAuditRunner

from tests.git_helpers import init_git_repo


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_a_clean_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"requirements.txt": "pyyaml==6.0.2\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"requirements.txt": "pyyaml==5.3\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "pyyaml" and v["severity"] == "MEDIUM" for v in vulnerabilities)


def test_reports_a_failed_audit_when_resolution_fails(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"requirements.txt": "this-package-does-not-exist-radar-xyz==1.0.0\n"}
    )

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert "error" in result.raw_output
    assert "vulnerabilities" not in result.raw_output


def test_reports_tool_identity():
    runner = PipAuditRunner()

    assert runner.tool_name == "pip-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
