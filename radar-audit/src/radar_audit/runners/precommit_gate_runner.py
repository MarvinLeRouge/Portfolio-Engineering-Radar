from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import yaml

from radar_audit.runner import RawToolOutput

_PRECOMMIT_CONFIG_FILENAME = ".pre-commit-config.yaml"
_HUSKY_DIRNAME = ".husky"
_HUSKY_HOOK_FILENAME = "pre-commit"
_LEFTHOOK_CONFIG_FILENAME = "lefthook.yml"
_STRIPPED_TOKENS = ("npx", "npm", "exec")


class PreCommitGateRunner:
    """Detects the pre-commit hook framework and extracts raw hook/command evidence
    (criterion 2.4). No subprocess -- pure filesystem + config parsing.
    """

    tool_name = "pre-commit-gate"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 10

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        precommit_config = target_path / _PRECOMMIT_CONFIG_FILENAME
        husky_dir = target_path / _HUSKY_DIRNAME
        lefthook_config = target_path / _LEFTHOOK_CONFIG_FILENAME

        if precommit_config.is_file():
            tier, entries = "pre-commit", self._parse_precommit_config(precommit_config)
        elif husky_dir.is_dir():
            tier, entries = "husky", self._parse_husky(target_path, husky_dir)
        elif lefthook_config.is_file():
            tier, entries = "lefthook", self._parse_lefthook(lefthook_config)
        else:
            tier, entries = "none", []

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"filesystem-check {target_path}",
            raw_output={"tier": tier, "entries": entries},
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _parse_precommit_config(self, config_path: Path) -> list[dict[str, str | None]]:
        data = yaml.safe_load(config_path.read_text()) or {}
        entries: list[dict[str, str | None]] = []
        for repo in data.get("repos", []) or []:
            for hook in repo.get("hooks", []) or []:
                hook_id = hook.get("id")
                if hook_id:
                    entries.append({"id": hook_id, "files": hook.get("files")})
        return entries

    def _parse_husky(self, target_path: Path, husky_dir: Path) -> list[dict[str, str | None]]:
        hook_file = husky_dir / _HUSKY_HOOK_FILENAME
        if not hook_file.is_file() or "lint-staged" not in hook_file.read_text():
            return []

        package_json = target_path / "package.json"
        if not package_json.is_file():
            return []

        data = json.loads(package_json.read_text())
        lint_staged = data.get("lint-staged")
        if not isinstance(lint_staged, dict):
            return []

        entries: list[dict[str, str | None]] = []
        for pattern, commands in lint_staged.items():
            command_list = commands if isinstance(commands, list) else [commands]
            for command in command_list:
                tool_id = self._extract_tool_id(command)
                if tool_id:
                    entries.append({"id": tool_id, "files": pattern})
        return entries

    def _parse_lefthook(self, config_path: Path) -> list[dict[str, str | None]]:
        data = yaml.safe_load(config_path.read_text()) or {}
        entries: list[dict[str, str | None]] = []
        for hook_config in data.values():
            if not isinstance(hook_config, dict):
                continue
            for command_config in (hook_config.get("commands") or {}).values():
                if not isinstance(command_config, dict):
                    continue
                run_command = command_config.get("run")
                tool_id = self._extract_tool_id(run_command) if run_command else None
                if tool_id:
                    entries.append({"id": tool_id, "files": None})
        return entries

    def _extract_tool_id(self, command: str) -> str | None:
        for token in command.split():
            basename = token.rsplit("/", 1)[-1]
            if basename in _STRIPPED_TOKENS:
                continue
            return basename
        return None
