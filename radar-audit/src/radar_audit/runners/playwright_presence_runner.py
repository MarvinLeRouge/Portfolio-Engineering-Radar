from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_CONFIG_FILENAMES = ("playwright.config.js", "playwright.config.ts")


class PlaywrightPresenceRunner:
    """Detects Playwright E2E test setup via config file or devDependency presence
    (criterion 3.3, JavaScript). No subprocess -- spec §6.
    """

    tool_name = "playwright-presence"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        present = any((target_path / filename).exists() for filename in _CONFIG_FILENAMES)
        if not present:
            present = self._has_devdependency(target_path)

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"playwright-presence-check {target_path}",
            raw_output={"present": present},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _has_devdependency(self, target_path: Path) -> bool:
        package_json = target_path / "package.json"
        if not package_json.exists():
            return False
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return False
        return "@playwright/test" in data.get("devDependencies", {})
