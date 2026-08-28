from radar_audit.discovery import SubProject, discover_subprojects

from tests.git_helpers import init_git_repo


def test_single_python_repo_yields_one_subproject_at_root(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname='x'\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="python")]


def test_repo_with_no_manifest_yields_one_unknown_subproject(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"README.md": "hello\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="unknown")]


def test_monorepo_with_first_level_manifests_yields_one_subproject_per_dir(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "backend/pyproject.toml": "[project]\nname='backend'\n",
            "frontend/package.json": "{}\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert sorted(result, key=lambda sp: sp.path) == sorted(
        [
            SubProject(path=repo_path / "backend", stack="python"),
            SubProject(path=repo_path / "frontend", stack="javascript"),
        ],
        key=lambda sp: sp.path,
    )


def test_root_and_first_level_manifests_both_detected(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pyproject.toml": "[project]\nname='root'\n",
            "radar-core/pyproject.toml": "[project]\nname='radar-core'\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert sorted(result, key=lambda sp: sp.path) == sorted(
        [
            SubProject(path=repo_path, stack="python"),
            SubProject(path=repo_path / "radar-core", stack="python"),
        ],
        key=lambda sp: sp.path,
    )


def test_php_manifest_detected(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"composer.json": "{}\n"})

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="php")]


def test_requirements_txt_maps_to_python_and_does_not_duplicate(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "pyproject.toml": "[project]\nname='x'\n",
            "requirements.txt": "requests\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="python")]


def test_dot_directories_are_ignored(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "README.md": "hello\n",
            ".venv/pyvenv.cfg": "home = /usr\n",
        },
    )

    result = discover_subprojects(repo_path)

    assert result == [SubProject(path=repo_path, stack="unknown")]
