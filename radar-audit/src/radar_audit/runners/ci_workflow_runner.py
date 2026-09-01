from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Literal

import yaml

from radar_audit.runner import RawToolOutput

_TEST_KEYWORDS = (
    "pytest",
    "vitest",
    "npm test",
    "npm run test",
    "pnpm test",
    "pest",
    "phpunit",
    "php artisan test",
)
_PLAYWRIGHT_KEYWORDS = ("playwright test", "npx playwright test")

# Matches an indirect invocation through a package.json script, e.g.
# "npm run test:e2e", "yarn test:coverage", "pnpm run test:e2e" -- resolved
# against package.json's "scripts" so a step whose literal text carries no
# test/Playwright keyword (because it is hidden behind a script name) is
# still detected via the script's own command.
_NPM_RUN_SCRIPT_RE = re.compile(
    r"\b(?:npm run(?:-script)?|yarn(?: run)?|pnpm(?: run)?)\s+([\w:.-]+)"
)


class CiWorkflowRunner:
    """Parses .github/workflows/*.yml directly with PyYAML for test-invocation and
    Playwright keywords, feeding both criterion 3.3 (E2E) and 3.4 (CI test execution)
    from a single pass -- spec §6. No subprocess, always exit_code 0: presence/absence
    is encoded in raw_output, not in the runner's own success/failure.

    A step's `run:` text is scanned directly, and also resolved one level through
    package.json's "scripts" when it invokes `npm run <script>` / `yarn <script>` /
    `pnpm run <script>` -- real workflows commonly hide the actual test/Playwright
    command behind a script name (e.g. `npm run test:e2e` -> `playwright test`).
    """

    tool_name = "ci-workflow"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        workflows_dir = target_path / ".github" / "workflows"
        workflow_files: list[Path] = []
        if workflows_dir.is_dir():
            workflow_files = sorted(
                p for p in workflows_dir.iterdir() if p.suffix in {".yml", ".yaml"} and p.is_file()
            )

        package_scripts = self._load_package_scripts(target_path)

        test_execution_found = False
        playwright_execution_found = False
        for workflow_file in workflow_files:
            for run_value in self._run_steps(workflow_file):
                for candidate in (run_value, *self._resolved_scripts(run_value, package_scripts)):
                    lowered = candidate.lower()
                    if any(keyword in lowered for keyword in _TEST_KEYWORDS):
                        test_execution_found = True
                    if any(keyword in lowered for keyword in _PLAYWRIGHT_KEYWORDS):
                        playwright_execution_found = True

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"ci-workflow-parse {workflows_dir}",
            raw_output={
                "workflows_found": len(workflow_files),
                "test_execution_found": test_execution_found,
                "playwright_execution_found": playwright_execution_found,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _run_steps(self, workflow_file: Path) -> list[str]:
        try:
            content = yaml.safe_load(workflow_file.read_text(errors="ignore"))
        except yaml.YAMLError:
            return []
        if not isinstance(content, dict):
            return []

        jobs = content.get("jobs", {})
        if not isinstance(jobs, dict):
            return []

        run_values: list[str] = []
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps", [])
            if not isinstance(steps, list):
                continue
            for step in steps:
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    run_values.append(step["run"])
        return run_values

    def _load_package_scripts(self, target_path: Path) -> dict[str, str]:
        package_json = target_path / "package.json"
        if not package_json.exists():
            return {}
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return {}
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            return {}
        return {name: command for name, command in scripts.items() if isinstance(command, str)}

    def _resolved_scripts(self, run_value: str, package_scripts: dict[str, str]) -> list[str]:
        if not package_scripts:
            return []
        resolved: list[str] = []
        for script_name in _NPM_RUN_SCRIPT_RE.findall(run_value):
            command = package_scripts.get(script_name)
            if command:
                resolved.append(command)
        return resolved
