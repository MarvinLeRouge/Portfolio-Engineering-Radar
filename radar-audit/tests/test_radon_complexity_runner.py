from radar_audit.runners.radon_complexity_runner import RadonComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_FUNCTION = "def add(a, b):\n    return a + b\n"

_COMPLEX_FUNCTION = (
    "def classify(n):\n"
    + "".join(f"    if n == {i}:\n        return {i}\n" for i in range(15))
    + "    return -1\n"
)


def test_reports_low_complexity_on_a_simple_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _SIMPLE_FUNCTION})

    runner = RadonComplexityRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    blocks = next(iter(result.raw_output.values()))
    assert blocks[0]["complexity"] <= 2


def test_reports_high_complexity_on_a_branchy_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _COMPLEX_FUNCTION})

    runner = RadonComplexityRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    blocks = next(iter(result.raw_output.values()))
    assert blocks[0]["complexity"] >= 11


def test_reports_tool_identity():
    runner = RadonComplexityRunner()

    assert runner.tool_name == "radon-cc"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
