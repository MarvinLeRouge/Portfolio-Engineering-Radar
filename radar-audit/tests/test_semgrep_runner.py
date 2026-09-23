from radar_audit.runners.semgrep_runner import SemgrepRunner

from tests.git_helpers import init_git_repo


def test_reports_no_findings_on_clean_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a, b):\n    return a + b\n"})

    runner = SemgrepRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["results"] == []


def test_reports_a_finding_for_shell_true_subprocess(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/vuln.py": (
                "import subprocess\n\n"
                "def run_cmd(user_input):\n"
                "    subprocess.run(user_input, shell=True)\n"
            )
        },
    )

    runner = SemgrepRunner()
    result = runner.run(repo_path, exclude_paths=[])

    results = result.raw_output["results"]
    assert len(results) >= 1
    assert any("shell" in r["check_id"] for r in results)
    assert results[0]["extra"]["severity"] in {"ERROR", "WARNING", "INFO"}


def test_reports_tool_identity():
    runner = SemgrepRunner()

    assert runner.tool_name == "semgrep"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
