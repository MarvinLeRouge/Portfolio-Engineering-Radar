import pytest
from radar_audit.config import PortfolioConfigError, load_portfolio_config


def _write_yaml(tmp_path, content):
    path = tmp_path / "portfolio.yaml"
    path.write_text(content)
    return path


def test_load_portfolio_config_reads_repos_root_and_repositories(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
        repos_root: /home/example/projets
        repositories:
          - name: RepoOne
          - name: RepoTwo
        """,
    )

    config = load_portfolio_config(path)

    assert config.repos_root == __import__("pathlib").Path("/home/example/projets")
    assert config.repositories == ["RepoOne", "RepoTwo"]


def test_load_portfolio_config_expands_user_in_repos_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = _write_yaml(
        tmp_path,
        """
        repos_root: ~/projets
        repositories:
          - name: RepoOne
        """,
    )

    config = load_portfolio_config(path)

    assert config.repos_root == tmp_path / "projets"


def test_load_portfolio_config_missing_repos_root_raises(tmp_path):
    path = _write_yaml(tmp_path, "repositories:\n  - name: RepoOne\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_load_portfolio_config_missing_repositories_raises(tmp_path):
    path = _write_yaml(tmp_path, "repos_root: /home/example/projets\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_load_portfolio_config_empty_repositories_raises(tmp_path):
    path = _write_yaml(tmp_path, "repos_root: /home/example/projets\nrepositories: []\n")

    with pytest.raises(PortfolioConfigError):
        load_portfolio_config(path)


def test_resolve_repo_path_returns_repos_root_joined_with_name(tmp_path):
    path = _write_yaml(
        tmp_path,
        f"""
        repos_root: {tmp_path}
        repositories:
          - name: RepoOne
        """,
    )
    config = load_portfolio_config(path)

    assert config.resolve_repo_path("RepoOne") == (tmp_path / "RepoOne").resolve()


def test_resolve_repo_path_unknown_repo_raises(tmp_path):
    path = _write_yaml(
        tmp_path,
        f"""
        repos_root: {tmp_path}
        repositories:
          - name: RepoOne
        """,
    )
    config = load_portfolio_config(path)

    with pytest.raises(PortfolioConfigError):
        config.resolve_repo_path("Unknown")
