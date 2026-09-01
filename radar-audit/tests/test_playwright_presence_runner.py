from radar_audit.runners.playwright_presence_runner import PlaywrightPresenceRunner

from tests.git_helpers import init_git_repo


def test_detects_presence_via_config_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"playwright.config.ts": "export default {};\n", "package.json": "{}\n"},
    )

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is True


def test_detects_presence_via_devdependency_only(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": (
                '{"name": "fixture", "devDependencies": {"@playwright/test": "^1.40.0"}}\n'
            )
        },
    )

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is True


def test_reports_absent_when_neither_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"package.json": '{"name": "fixture"}\n'})

    runner = PlaywrightPresenceRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["present"] is False


def test_reports_tool_identity():
    runner = PlaywrightPresenceRunner()

    assert runner.tool_name == "playwright-presence"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
