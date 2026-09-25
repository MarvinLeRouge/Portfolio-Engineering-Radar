import pytest
from radar_audit.runners.phpdoc_checker_runner import PhpdocCheckerRunner

from tests.git_helpers import init_git_repo

_DOCUMENTED_CLASS = (
    "<?php\n\n/**\n * Class A.\n */\nclass A\n{\n"
    "    /**\n     * Add two numbers.\n     *\n     * @param int $a\n     * @param int $b\n"
    "     * @return int\n     */\n    public function add(int $a, int $b): int\n    {\n"
    "        return $a + $b;\n    }\n}\n"
)

_UNDOCUMENTED_CLASS = (
    "<?php\n\nclass B\n{\n    public function subtract(int $a, int $b): int\n"
    "    {\n        return $a - $b;\n    }\n}\n"
)


@pytest.mark.slow
def test_reports_no_findings_on_a_fully_documented_class(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _DOCUMENTED_CLASS})

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["findings"] == []


@pytest.mark.slow
def test_reports_class_and_method_findings_on_an_undocumented_class(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/B.php": _UNDOCUMENTED_CLASS})

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    types = {f["type"] for f in result.raw_output["findings"]}
    assert "class" in types
    assert "method" in types


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/A.php": _DOCUMENTED_CLASS,
            "src/excluded/B.php": _UNDOCUMENTED_CLASS,
        },
    )

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    findings = result.raw_output["findings"]
    assert not any("excluded" in f["file"] for f in findings)


def test_reports_tool_identity():
    runner = PhpdocCheckerRunner()

    assert runner.tool_name == "phpdoc-checker"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
