from radar_audit.runners.dependency_cruiser_runner import DependencyCruiserRunner

from tests.git_helpers import init_git_repo


def test_reports_no_circular_dependencies_on_a_clean_tree(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export const a = 1;\n",
            "src/b.js": "import { a } from './a.js';\nexport const b = a + 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    circular_deps = [d for m in modules for d in m["dependencies"] if d["circular"]]
    assert circular_deps == []


def test_detects_a_circular_import(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "import { b } from './b.js';\nexport const a = 1;\n",
            "src/b.js": "import { a } from './a.js';\nexport const b = 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    circular_deps = [d for m in modules for d in m["dependencies"] if d["circular"]]
    assert len(circular_deps) == 2  # a->b and b->a each flagged


def test_excludes_node_modules_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export const a = 1;\n",
            "node_modules/pkg/a.js": "import { b } from './b.js';\nexport const a = 1;\n",
            "node_modules/pkg/b.js": "import { a } from './a.js';\nexport const b = 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    assert all("node_modules" not in m["source"] for m in modules)


def test_reports_tool_identity():
    runner = DependencyCruiserRunner()

    assert runner.tool_name == "dependency-cruiser"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
