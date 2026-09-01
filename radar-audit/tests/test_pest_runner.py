import subprocess

import pytest
from radar_audit.runners.pest_runner import PestRunner

from tests.git_helpers import init_git_repo

_PHPUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
>
    <testsuites>
        <testsuite name="Test Suite">
            <directory suffix="Test.php">./tests</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>src</directory>
        </include>
    </source>
</phpunit>
"""

_CALCULATOR_PHP = """<?php

class Calculator
{
    public function add(int $a, int $b): int
    {
        return $a + $b;
    }
}
"""


def _install_local_pest(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"pestphp/pest": "^3.0"}, '
        '"config": {"allow-plugins": {"pestphp/pest-plugin": true}}}\n'
    )
    subprocess.run(
        ["composer", "install", "--no-interaction"],
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
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(3);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
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
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(4);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "tests/Unit/CalculatorTest.php"


@pytest.mark.slow
def test_reports_zero_collected_as_no_tests(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            # A tests/ directory that exists but has no discoverable test file --
            # this is Pest's genuine "zero collected" case (exit 0, bare
            # <testsuites/> report). Omitting the tests/ directory entirely
            # instead makes Pest exit 2 with "Test directory not found", which
            # is a misconfiguration error, not a zero-tests result.
            "tests/Helper.php": "<?php\n// not a test file\n",
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 0


@pytest.mark.slow
def test_reports_fallback_when_tests_directory_missing(tmp_path):
    """Pest writes a 0-byte junit.xml (not "file absent") and exits 2 when its
    configured tests/ directory doesn't exist -- verify the ParseError guard falls
    back to the contracted raw_output shape instead of crashing.
    """
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"phpunit.xml": _PHPUNIT_XML, "src/Calculator.php": _CALCULATOR_PHP},
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 2
    assert result.raw_output == {
        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": None,
    }


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/Calculator.php": "<?php\n"})

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PestRunner()

    assert runner.tool_name == "pest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
