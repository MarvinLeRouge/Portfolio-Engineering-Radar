from radar_audit.runners.semgrep_runner import SemgrepRunner, _scan_succeeded

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


def test_scan_with_fatal_errors_and_no_results_is_a_failure():
    # Shape observed from a real rule download failure (exit code 7).
    data = {
        "results": [],
        "errors": [{"code": 2, "level": "error", "type": "SemgrepError", "message": "HTTP 404"}],
    }

    assert _scan_succeeded(data, returncode=0) is False
    assert _scan_succeeded(data, returncode=7) is False


def test_hard_failure_exit_code_is_a_failure_even_without_errors():
    assert _scan_succeeded({"results": [], "errors": []}, returncode=2) is False


def test_non_json_output_is_a_failure():
    assert _scan_succeeded(None, returncode=0) is False


def test_per_file_parse_warnings_do_not_invalidate_a_clean_scan():
    data = {"results": [], "errors": [{"code": 3, "level": "warn", "type": "Syntax error"}]}

    assert _scan_succeeded(data, returncode=0) is True


def test_reports_a_failed_scan_when_rules_cannot_be_downloaded(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})
    # An unreachable registry makes the `--config auto` rule download fail (exit 2).
    monkeypatch.setenv("SEMGREP_URL", "http://127.0.0.1:9")

    runner = SemgrepRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert "error" in result.raw_output
    assert "results" not in result.raw_output


def test_reports_tool_identity():
    runner = SemgrepRunner()

    assert runner.tool_name == "semgrep"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
