from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import yaml

from radar_audit.runner import RawToolOutput

_TEST_KEYWORDS = ("pytest", "vitest", "npm test", "pnpm test", "pest", "phpunit")
_PLAYWRIGHT_KEYWORDS = ("playwright test", "npx playwright test")


class CiWorkflowRunner:
    """Parses .github/workflows/*.yml directly with PyYAML for test-invocation and
    Playwright keywords, feeding both criterion 3.3 (E2E) and 3.4 (CI test execution)
    from a single pass -- spec §6. No subprocess, always exit_code 0: presence/absence
    is encoded in raw_output, not in the runner's own success/failure.
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

        test_execution_found = False
        playwright_execution_found = False
        for workflow_file in workflow_files:
            for run_value in self._run_steps(workflow_file):
                lowered = run_value.lower()
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
