import pytest
from radar_audit.runners.phpmd_complexity_runner import PhpmdComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_METHOD = (
    "<?php\n\nclass A\n{\n    public function add(int $a, int $b): int\n"
    "    {\n        return $a + $b;\n    }\n}\n"
)

_COMPLEX_METHOD_BODY = "".join(f"        if ($n === {i}) return {i};\n" for i in range(15))
_COMPLEX_METHOD = (
    "<?php\n\nclass A\n{\n    public function classify(int $n): int\n    {\n"
    + _COMPLEX_METHOD_BODY
    + "        return -1;\n    }\n}\n"
)


@pytest.mark.slow
def test_reports_no_violations_on_a_simple_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _SIMPLE_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["violations"] == []


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _COMPLEX_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    violations = result.raw_output["violations"]
    assert violations and max(v["complexity"] for v in violations) >= 11


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/A.php": _COMPLEX_METHOD,
            "src/excluded/B.php": _COMPLEX_METHOD,
        },
    )

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "src" / "excluded"])

    violations = result.raw_output["violations"]

    # Verify that the excluded file's violations are not in the output
    excluded_files = [v["file"] for v in violations if "excluded" in v["file"]]
    assert len(excluded_files) == 0, "Excluded directory should have no violations reported"

    # Verify that non-excluded violations ARE still present (not over-broad exclusion)
    non_excluded_violations = [v["file"] for v in violations if "excluded" not in v["file"]]
    assert len(non_excluded_violations) > 0, "Non-excluded file's violations should be present"


def test_reports_tool_identity():
    runner = PhpmdComplexityRunner()

    assert runner.tool_name == "phpmd-codesize"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
