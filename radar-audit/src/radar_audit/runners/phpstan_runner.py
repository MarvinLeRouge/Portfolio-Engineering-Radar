from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PhpstanRunner:
    """Runs PHPStan (criterion 2.2, PHP) via a mutate-target/revert workaround for Larastan."""

    tool_name = "phpstan"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        composer_json = target_path / "composer.json"
        composer_lock = target_path / "composer.lock"
        original_json = composer_json.read_bytes() if composer_json.exists() else None
        original_lock = composer_lock.read_bytes() if composer_lock.exists() else None

        is_laravel = self._is_laravel(composer_json)
        dev_packages = ["phpstan/phpstan"]
        if is_laravel:
            dev_packages.append("larastan/larastan")

        start = time.monotonic()
        try:
            subprocess.run(
                ["composer", "require", "--dev", *dev_packages, "--no-interaction"],
                cwd=target_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            extension_neon = target_path / "_radar_audit_phpstan.neon"
            neon_content = self._build_neon_content(
                is_laravel=is_laravel, target_path=target_path, exclude_paths=exclude_paths
            )
            extension_neon.write_text(neon_content)
            try:
                command = [
                    "vendor/bin/phpstan",
                    "analyse",
                    "--configuration",
                    str(extension_neon),
                    "--error-format=json",
                    "--no-progress",
                    str(target_path),
                ]
                completed = subprocess.run(
                    command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
                )
            finally:
                extension_neon.unlink(missing_ok=True)
        finally:
            if original_json is not None:
                composer_json.write_bytes(original_json)
            else:
                composer_json.unlink(missing_ok=True)
            if original_lock is not None:
                composer_lock.write_bytes(original_lock)
            else:
                composer_lock.unlink(missing_ok=True)
            subprocess.run(
                ["composer", "install", "--no-interaction"],
                cwd=target_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _is_laravel(self, composer_json: Path) -> bool:
        if not composer_json.exists():
            return False
        data = json.loads(composer_json.read_text())
        return "laravel/framework" in data.get("require", {})

    def _build_neon_content(
        self, is_laravel: bool, target_path: Path, exclude_paths: list[Path]
    ) -> str:
        """Build the PHPStan neon config, always excluding the target's own vendor/.

        PHPStan has no CLI flag to skip a directory, only `parameters.excludePaths`
        in its config (docs/toolchain.md). Without it, analysing `target_path`
        picks up third-party code under its own `vendor/`, including the
        `phpstan/phpstan`/`larastan/larastan` packages this runner just installed
        there, producing noise unrelated to the target's own code.
        """
        exclude_entries = [str(target_path / "vendor" / "*")]
        exclude_entries.extend(str(excluded / "*") for excluded in exclude_paths)

        lines: list[str] = []
        if is_laravel:
            lines.append("includes:")
            lines.append("    - vendor/larastan/larastan/extension.neon")
        lines.append("parameters:")
        lines.append("    level: 5")
        lines.append("    excludePaths:")
        for entry in exclude_entries:
            lines.append(f"        - {entry}")
        return "\n".join(lines) + "\n"
