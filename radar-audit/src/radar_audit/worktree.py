from __future__ import annotations

import subprocess
from pathlib import Path


def compute_exclude_paths(repo_path: Path) -> list[Path]:
    """Return every worktree path linked to `repo_path`'s repo, excluding `repo_path` itself."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )

    all_paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]

    main_path = repo_path.resolve()
    return [path for path in all_paths if path != main_path]
