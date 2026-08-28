import subprocess

from radar_core.models.repository import Repository
from sqlmodel import select

from tests.git_helpers import init_git_repo


def test_init_git_repo_creates_a_repo_with_one_commit(tmp_path):
    repo_path = tmp_path / "sample-repo"
    init_git_repo(repo_path)

    log = subprocess.run(
        ["git", "-C", str(repo_path), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log.stdout.strip().splitlines()) == 1


def test_init_git_repo_writes_requested_files(tmp_path):
    repo_path = tmp_path / "sample-repo"
    init_git_repo(repo_path, files={"pyproject.toml": "[project]\nname = 'x'\n"})

    assert (repo_path / "pyproject.toml").read_text() == "[project]\nname = 'x'\n"


def test_db_session_fixture_has_migrated_schema(db_session):
    repository = Repository(name="example", path="/tmp/example")
    db_session.add(repository)
    db_session.commit()

    found = db_session.exec(select(Repository).where(Repository.name == "example")).first()
    assert found is not None
    assert found.path == "/tmp/example"
