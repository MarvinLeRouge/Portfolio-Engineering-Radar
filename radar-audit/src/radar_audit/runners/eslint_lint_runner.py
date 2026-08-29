# src/radar_audit/runners/eslint_lint_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class EslintLintRunner:
    """Runs the target's own lint script through an ephemeral ESLint (criterion 2.1)."""

    tool_name = "eslint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        scope_tokens = self._resolve_lint_scope(target_path)

        # Filter out scope tokens that are under excluded paths to avoid conflicts
        # where ESLint would be asked to lint and then ignore the same path
        filtered_tokens = []
        for token in scope_tokens:
            token_path = target_path / token
            is_excluded = any(
                token_path == excluded or token_path in excluded.parents
                for excluded in exclude_paths
            )
            if not is_excluded:
                filtered_tokens.append(token)

        # If all tokens were filtered, fall back to "."
        scope_tokens = filtered_tokens if filtered_tokens else ["."]

        command = ["npx", "--package=eslint", "--", "eslint", *scope_tokens, "--format", "json"]

        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue
            command.extend(["--ignore-pattern", f"{relative}/**"])

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"results": results},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _resolve_lint_scope(self, target_path: Path) -> list[str]:
        package_json = target_path / "package.json"
        if not package_json.exists():
            return ["."]

        data = json.loads(package_json.read_text())
        lint_script = data.get("scripts", {}).get("lint", "")
        tokens = [
            token
            for token in lint_script.split()
            if not token.startswith("-") and token != "eslint"
        ]
        resolved = [token for token in tokens if (target_path / token).exists()]
        return resolved if resolved else ["."]
