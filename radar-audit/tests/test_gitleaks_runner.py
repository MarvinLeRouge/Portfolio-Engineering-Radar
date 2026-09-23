from radar_audit.runners.gitleaks_runner import GitleaksRunner

from tests.git_helpers import init_git_repo

# A high-entropy fake secret shaped like a GitHub PAT - gitleaks' rules include an
# entropy threshold, so a low-entropy/sequential placeholder does not trigger a hit
# (confirmed empirically).
_HIGH_ENTROPY_TOKEN = "ghp_NbrnTP3fAbnFbmOHnKYaXRvj7uff0LYTH8xI"


def test_reports_no_findings_on_a_clean_repo(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = GitleaksRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"findings": []}


def test_reports_a_finding_for_a_committed_secret(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"config.py": f'API_KEY = "{_HIGH_ENTROPY_TOKEN}"\n'})

    runner = GitleaksRunner()
    result = runner.run(repo_path, exclude_paths=[])

    findings = result.raw_output["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == "github-pat"
    assert findings[0]["file"] == "config.py"
    assert findings[0]["line"] == 1


def test_reports_tool_identity():
    runner = GitleaksRunner()

    assert runner.tool_name == "gitleaks"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
