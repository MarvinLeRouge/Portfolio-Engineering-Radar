from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PortfolioConfigError(ValueError):
    """Raised when portfolio.yaml is missing required fields or malformed."""


@dataclass(frozen=True)
class PortfolioConfig:
    repos_root: Path
    repositories: list[str]

    def resolve_repo_path(self, name: str) -> Path:
        if name not in self.repositories:
            raise PortfolioConfigError(f"Repository '{name}' is not listed in portfolio.yaml")
        return (self.repos_root / name).resolve()


def load_portfolio_config(path: Path) -> PortfolioConfig:
    raw: Any = yaml.safe_load(path.read_text())

    if not isinstance(raw, dict) or "repos_root" not in raw:
        raise PortfolioConfigError(f"{path} must define 'repos_root'")
    if "repositories" not in raw or not raw["repositories"]:
        raise PortfolioConfigError(f"{path} must define a non-empty 'repositories' list")

    repos_root = Path(str(raw["repos_root"])).expanduser()
    repositories = [str(entry["name"]) for entry in raw["repositories"]]

    return PortfolioConfig(repos_root=repos_root, repositories=repositories)
