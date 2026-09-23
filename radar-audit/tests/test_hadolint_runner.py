from radar_audit.runners.hadolint_runner import HadolintRunner

from tests.git_helpers import init_git_repo


def test_reports_no_dockerfiles(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"dockerfiles": []}


def test_reports_a_clean_dockerfile(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"Dockerfile": 'FROM alpine:3.19\nCMD ["echo", "hi"]\n'},
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert dockerfiles[0]["path"] == "Dockerfile"
    assert dockerfiles[0]["findings"] == []


def test_reports_findings_for_an_unpinned_apt_install(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"Dockerfile": "FROM ubuntu:20.04\nRUN apt-get update && apt-get install -y curl\n"},
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert len(dockerfiles[0]["findings"]) > 0
    assert any(f["code"] == "DL3008" for f in dockerfiles[0]["findings"])


def test_excludes_vendored_dockerfiles(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "Dockerfile": "FROM alpine:3.19\n",
            "vendor/laravel/sail/runtimes/8.2/Dockerfile": "FROM ubuntu:20.04\n",
        },
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert dockerfiles[0]["path"] == "Dockerfile"


def test_marks_a_dockerfile_as_failed_when_docker_is_unreachable(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"Dockerfile": "FROM ubuntu:20.04\nRUN apt-get update && apt-get install -y curl\n"},
    )
    monkeypatch.setenv("DOCKER_HOST", f"unix://{tmp_path}/nonexistent.sock")

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code != 0
    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert "error" in dockerfiles[0]
    assert "findings" not in dockerfiles[0]


def test_reports_tool_identity():
    runner = HadolintRunner()

    assert runner.tool_name == "hadolint"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
