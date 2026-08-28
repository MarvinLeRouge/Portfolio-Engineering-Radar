from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(path: Path, files: dict[str, str] | None = None) -> None:
    """Create a git repo with one commit at `path`, for use as a test fixture.

    `path` must not already exist. `files` maps relative file paths (created
    with any needed parent directories) to their text content.
    """
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)

    for relative_path, content in (files or {}).items():
        file_path = path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    if not files:
        (path / ".gitkeep").touch()

    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=path, check=True)
