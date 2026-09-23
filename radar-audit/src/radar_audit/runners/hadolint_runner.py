from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command

# Matches the discovery pitfall documented in toolchain.md: naive Dockerfile
# discovery on Summit-Stats surfaced vendored/third-party Dockerfiles (e.g.
# vendor/laravel/sail/runtimes/*/Dockerfile) as noise.
_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__", ".git"}


class HadolintRunner:
    """Lints every discovered Dockerfile with Hadolint (criterion 4.5)."""

    tool_name = "hadolint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        dockerfiles = self._discover_dockerfiles(target_path, exclude_paths)

        results = []
        total_duration_ms = 0
        for dockerfile in dockerfiles:
            completed, duration_ms = run_docker_command(
                ["-i", "hadolint/hadolint", "hadolint", "--format", "json", "-"],
                timeout_s=self.timeout_s,
                input_text=dockerfile.read_text(),
            )
            total_duration_ms += duration_ms
            try:
                findings = json.loads(completed.stdout)
            except json.JSONDecodeError:
                findings = []
            results.append({"path": str(dockerfile.relative_to(target_path)), "findings": findings})

        return RawToolOutput(
            command="docker run ... hadolint --format json -",
            raw_output={"dockerfiles": results},
            exit_code=0,
            duration_ms=total_duration_ms,
        )

    def _discover_dockerfiles(self, target_path: Path, exclude_paths: list[Path]) -> list[Path]:
        found = []
        for candidate in target_path.rglob("Dockerfile*"):
            if not candidate.is_file():
                continue
            relative_parts = candidate.relative_to(target_path).parts
            if any(part in _SKIP_DIRNAMES for part in relative_parts):
                continue
            if any(
                excluded == candidate or excluded in candidate.parents for excluded in exclude_paths
            ):
                continue
            found.append(candidate)
        return sorted(found)
