import subprocess

from radar_audit.runners.trivy_image_runner import TrivyImageRunner

from tests.git_helpers import init_git_repo


def test_reports_image_not_found_when_no_local_image_matches(tmp_path):
    repo_path = tmp_path / "repo-with-no-image"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = TrivyImageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"image_found": False}


def test_reports_vulnerabilities_when_a_matching_local_image_exists(tmp_path):
    repo_path = tmp_path / "trivyimgtest"
    init_git_repo(repo_path, files={"Dockerfile": "FROM alpine:latest\n"})
    image_tag = f"{repo_path.name.lower()}:latest"
    subprocess.run(
        ["docker", "build", "-t", image_tag, str(repo_path)], check=True, capture_output=True
    )
    try:
        runner = TrivyImageRunner()
        result = runner.run(repo_path, exclude_paths=[])

        assert result.raw_output["image_found"] is True
        assert result.raw_output["image"] == image_tag
        assert isinstance(result.raw_output["vulnerabilities"], list)
        for vuln in result.raw_output["vulnerabilities"]:
            assert vuln["severity"] in {"HIGH", "CRITICAL"}
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_reports_tool_identity():
    runner = TrivyImageRunner()

    assert runner.tool_name == "trivy-image"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
