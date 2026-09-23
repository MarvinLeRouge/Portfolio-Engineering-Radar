import json

from radar_audit.normalizers.secrets_in_history import _is_pre_filtered
from radar_audit.runners.gitleaks_runner import GitleaksRunner

from tests.git_helpers import init_git_repo

# A high-entropy fake secret shaped like a GitHub PAT - gitleaks' rules include an
# entropy threshold, so a low-entropy/sequential placeholder does not trigger a hit
# (confirmed empirically).
_HIGH_ENTROPY_TOKEN = "ghp_NbrnTP3fAbnFbmOHnKYaXRvj7uff0LYTH8xI"
# A high-entropy value with no provider prefix, caught by the generic-api-key rule.
_HIGH_ENTROPY_GENERIC_SECRET = "a8Kd93jfLq0ZpXv7Rt2mNw4bYc6HsE1u"


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


def test_redacts_the_secret_but_keeps_the_variable_name(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "config.py": f'API_KEY = "{_HIGH_ENTROPY_TOKEN}"\n',
            "tests/test_auth.py": f'fake_token = "{_HIGH_ENTROPY_GENERIC_SECRET}"\n',
        },
    )

    runner = GitleaksRunner()
    result = runner.run(repo_path, exclude_paths=[])

    serialized = json.dumps(result.raw_output)
    assert _HIGH_ENTROPY_TOKEN not in serialized
    assert _HIGH_ENTROPY_GENERIC_SECRET not in serialized
    by_file = {f["file"]: f for f in result.raw_output["findings"]}
    assert "REDACTED" in by_file["config.py"]["match"]
    fake = by_file["tests/test_auth.py"]
    assert fake["rule"] == "generic-api-key"
    assert fake["match"].startswith("fake_token")
    assert _is_pre_filtered(fake)


def test_reports_tool_identity():
    runner = GitleaksRunner()

    assert runner.tool_name == "gitleaks"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
