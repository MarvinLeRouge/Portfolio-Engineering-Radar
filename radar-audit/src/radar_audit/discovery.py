from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_MANIFEST_STACKS: dict[str, str] = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "javascript",
    "composer.json": "php",
}


@dataclass(frozen=True)
class SubProject:
    path: Path
    stack: str


def discover_subprojects(repo_path: Path) -> list[SubProject]:
    subprojects = [SubProject(path=repo_path, stack=stack) for stack in _manifests_at(repo_path)]

    for child in sorted(
        p for p in repo_path.iterdir() if p.is_dir() and not p.name.startswith(".")
    ):
        subprojects.extend(SubProject(path=child, stack=stack) for stack in _manifests_at(child))

    if not subprojects:
        return [SubProject(path=repo_path, stack="unknown")]

    return subprojects


def _manifests_at(directory: Path) -> list[str]:
    stacks: list[str] = []
    for manifest_name, stack in _MANIFEST_STACKS.items():
        if (directory / manifest_name).is_file() and stack not in stacks:
            stacks.append(stack)
    return stacks
