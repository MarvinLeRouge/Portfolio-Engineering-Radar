import subprocess

import pytest
from radar_audit.runners.vitest_runner import VitestRunner

from tests.git_helpers import init_git_repo


def _install_local_vitest(repo_path, with_coverage=True):
    dev_deps = '"vitest": "^3.2.7"'
    if with_coverage:
        dev_deps += ', "@vitest/coverage-v8": "^3.2.7"'
    (repo_path / "package.json").write_text(
        '{"name": "fixture", "version": "1.0.0", "type": "module", '
        '"devDependencies": {' + dev_deps + "}}\n"
    )
    subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_pass_and_coverage_on_passing_suite(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


@pytest.mark.slow
def test_reports_failures_with_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(4); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] is not None


@pytest.mark.slow
def test_reports_no_coverage_percent_when_provider_absent(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path, with_coverage=False)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["coverage_percent"] is None


@pytest.mark.slow
def test_excludes_a_nested_worktree_from_test_discovery(tmp_path):
    # Real-world shape found auditing Summit-Stats: a `.claude/worktrees/<branch>/`
    # git worktree checked out inside the repo carries its own copy of the test
    # suite (plus, in that case, stale Playwright .spec.js files that don't parse
    # as Vitest tests at all) -- Vitest's default glob recurses the whole tree and
    # picks it up a second time unless exclude_paths is forwarded as --exclude.
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
            "nested-worktree/src/add.test.js": (
                'import { expect, test } from "vitest";\n\n'
                'test("duplicate", () => { expect(1).toBe(1); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    excluded_path = repo_path / "nested-worktree"

    result_without_exclude = runner.run(repo_path, exclude_paths=[])
    result_with_exclude = runner.run(repo_path, exclude_paths=[excluded_path])

    assert result_without_exclude.raw_output["tests"]["total"] == 2
    assert result_with_exclude.raw_output["tests"]["total"] == 1


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.js": "export function add() {}\n"})

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = VitestRunner()

    assert runner.tool_name == "vitest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
