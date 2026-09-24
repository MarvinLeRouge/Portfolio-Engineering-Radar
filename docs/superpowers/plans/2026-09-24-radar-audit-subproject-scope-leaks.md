# radar-audit: fix sibling-subproject scope leaks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop repo-root-scoped tool runners from scanning into a sibling subproject's
files (e.g. a JS-stack runner walking into `backend/`), and add the two related
hardcoded-exclusion gaps (build artifacts for `EslintComplexityRunner`, `htmlcov/` for
`StaticLocRunner`) that were previously masked by this leak.

**Architecture:** Three independent code changes in one branch, landed in dependency
order. (1) `orchestrator.py` gains a new helper that derives, for each planned run,
which other subprojects' paths are nested under that run's `target_path`, and passes
those as additional `exclude_paths` alongside the existing worktree-based ones — this is
the root-cause fix. (2) `EslintComplexityRunner` gets a hardcoded
`_ALWAYS_EXCLUDED_DIRNAMES` ignore list for `node_modules`/`dist`/`build`, matching the
pattern already used by `JscpdRunner`/`DependencyCruiserRunner`, independent of whatever
`exclude_paths` it's given. (3) `StaticLocRunner` adds `htmlcov` to its existing
`_SKIP_DIRNAMES` set. (1) is what actually stops the cross-subproject leak; (2) and (3)
close two artifact-exclusion gaps that were confirmed live but partly hidden behind (1)'s
bug in the audited data.

**Tech Stack:** Python 3, pytest, SQLModel (test DB via `db_session` fixture), existing
`ToolRunner` protocol.

**Spec:** No separate spec doc — this plan implements three already-diagnosed findings
from `docs/work-in-progress/report-review-findings.md` (#9 root cause, #3, #8's
`htmlcov/` part) per the branch breakdown in
`docs/work-in-progress/report-review-battle-plan.md`'s Phase 3 section. Both files travel
with this plan; executors should read the full finding write-ups (§9, §3, §8) before
starting, they contain the confirmed live-DB evidence this plan fixes.

## Global Constraints

- No AI-attribution trailer (`Co-Authored-By: Claude` or similar) in any commit message.
- Do not modify the GeoChallenge-Tracker repository itself (the tool's real-world test
  fixture) — this branch only touches `radar-audit/`.
- Follow existing code conventions exactly: `from __future__ import annotations` at the
  top of every touched file (already present), type hints matching the surrounding style,
  no reformatting unrelated lines.
- Test conventions: fast filesystem-walk runner tests (`StaticLocRunner`) have no
  `@pytest.mark.slow` marker; tests that shell out to real tools (`npx eslint`, real git)
  keep the existing marker/fixture pattern already used in their file.
- Push after each commit ([[feedback_auto_push]] project convention) — actually: this
  plan's executor pushes at the end of the branch's work, not after every single commit;
  local commits accumulate on the feature branch, a single `git push` (with upstream set)
  after the branch's tasks are done is sufficient, then PR per the project's
  PR-over-local-merge convention. (No local merge, ever.)

## Review Focus

- **Colocated subprojects at the same physical path** (e.g. a PHP+JS monorepo with no
  folder separation — already covered by
  `test_execute_audit_runs_multi_stack_runner_once_per_colocated_stacks`): the new
  subproject-exclusion logic must never exclude a run's own `target_path` just because
  another `SubProject` entry shares that exact path under a different stack. Covered by
  Task 1's test (asserts the JS-stack run at repo root still receives its own files).
- **Nesting direction must be one-way**: a subproject-scoped runner running *at* the
  nested path itself (e.g. the Python runner at `backend/`) must not have the repo root
  excluded from its own scan — only exclude subprojects nested *under* the current run's
  `target_path`, never the run's ancestors. Covered by Task 1's test (asserts the
  backend-path run's `exclude_paths` does not contain the repo root).
- **Worktree exclusions and subproject exclusions must combine, not replace each other**:
  the fix adds to `plan.exclude_paths`, it must not drop the existing worktree-derived
  entries. Existing `test_plan_audit_excludes_worktrees_from_subprojects` continues to
  pass unmodified (it tests `plan_audit`, untouched by this fix) as a regression guard;
  Task 1's own test uses a repo with no worktrees so it only exercises the new behavior in
  isolation, by design.
- **`EslintComplexityRunner`'s two exclusion mechanisms must not conflict**: the new
  hardcoded `_ALWAYS_EXCLUDED_DIRNAMES` `--ignore-pattern` flags and the existing
  per-`exclude_paths`-loop `--ignore-pattern` flags are both just repeated CLI flags to
  ESLint — no interaction expected, but Task 2's test passes a non-empty `exclude_paths`
  alongside a `dist/` fixture to confirm both apply together.
- **`StaticLocRunner`'s new `htmlcov` entry must match by directory component, not
  substring**: `_is_skipped` already checks `part in _SKIP_DIRNAMES` against
  `relative_parts`, so a file merely named `htmlcov_report.js` (not inside a directory
  literally named `htmlcov`) must still be counted. Task 3's test includes such a file to
  confirm no over-broad matching.

---

### Task 1: `orchestrator.py` — exclude sibling subprojects nested under each run's target path

**Files:**
- Modify: `radar-audit/src/radar_audit/orchestrator.py` (add `_subproject_exclusions`
  helper, wire it into `execute_audit`'s loop around line 167-180)
- Test: `radar-audit/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `AuditPlan.subprojects: list[SubProject]` (already exists, `SubProject` has
  `.path: Path` and `.stack: str`, from `radar_audit.discovery`), `PlannedRun.target_path:
  Path` (already exists).
- Produces: `_subproject_exclusions(target_path: Path, subprojects: list[SubProject]) ->
  list[Path]` — a private helper local to `orchestrator.py`, not consumed by any other
  task in this plan.

- [ ] **Step 1: Write failing test — sibling subproject nested under target path gets excluded, in both directions**

Add to `radar-audit/tests/test_orchestrator.py` (near the other `execute_audit` tests,
after `test_execute_audit_runs_multi_stack_runner_once_per_colocated_stacks`):

```python
class _RecordingRunner:
    tool_name = "recording-stub"
    tool_version = "0.0.1"
    supported_stacks: frozenset[str] = frozenset({"python", "javascript"})
    scope = "subproject"
    timeout_s = 10

    def __init__(self):
        self.calls: list[tuple] = []

    def run(self, target_path, exclude_paths):
        self.calls.append((target_path, list(exclude_paths)))
        return RawToolOutput(command="stub", raw_output={"ok": True}, exit_code=0, duration_ms=1)


def test_execute_audit_excludes_sibling_subproject_nested_under_target_path(
    db_session, tmp_path
):
    # JS subproject at repo root, Python subproject nested at backend/ -- mirrors
    # GeoChallenge-Tracker's real layout (finding #9).
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": "{}\n", "backend/pyproject.toml": "[project]\nname='x'\n"},
    )
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    runner = _RecordingRunner()

    execute_audit(db_session, config, "repo", [runner])

    backend_path = (repo_path / "backend").resolve()
    root_path = repo_path.resolve()
    root_call = next(c for c in runner.calls if c[0] == root_path)
    backend_call = next(c for c in runner.calls if c[0] == backend_path)

    # The root-scoped run must exclude the nested backend/ subproject.
    assert backend_path in root_call[1]
    # The backend-scoped run must NOT exclude its own ancestor (the repo root).
    assert root_path not in backend_call[1]


def test_execute_audit_does_not_exclude_colocated_same_path_subprojects(db_session, tmp_path):
    # PHP + JS manifests at the same physical path must not cause that path to
    # exclude itself.
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"package.json": "{}\n", "composer.json": "{}\n"})
    config = PortfolioConfig(repos_root=tmp_path, repositories=["repo"])
    runner = _RecordingRunner()

    execute_audit(db_session, config, "repo", [runner])

    root_path = repo_path.resolve()
    (call_target, call_excludes) = runner.calls[0]
    assert call_target == root_path
    assert root_path not in call_excludes
```

- [ ] **Step 2: Run tests, verify both fail**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -k "sibling_subproject or colocated_same_path" -v`
Expected: `test_execute_audit_excludes_sibling_subproject_nested_under_target_path` FAILs
(`backend_path in root_call[1]` is False, since `exclude_paths` is currently always
`plan.exclude_paths`, the worktree-only list — empty here, no worktrees). The second test
may already pass (nothing currently excludes anything), that's fine, it's a regression
guard for the fix about to be added, not a currently-broken behavior.

- [ ] **Step 3: Implement `_subproject_exclusions` and wire it into `execute_audit`**

In `radar-audit/src/radar_audit/orchestrator.py`, add the import and helper:

```python
from radar_audit.discovery import SubProject, discover_subprojects
```

(already imported — no change needed there, `SubProject` is already imported on line 13)

Add the helper function, placed after `_is_excluded` (around line 105-106):

```python
def _subproject_exclusions(target_path: Path, subprojects: list[SubProject]) -> list[Path]:
    """Every other subproject's path nested under `target_path`, so a runner scoped at
    `target_path` doesn't walk into a sibling subproject's files (e.g. a repo-root-scoped
    JS runner walking into a nested backend/ Python subproject). Never excludes
    `target_path` itself, even when another subproject shares that exact path (a
    colocated multi-stack subproject at the same physical directory).
    """
    resolved_target = target_path.resolve()
    exclusions = []
    for subproject in subprojects:
        resolved_subproject = subproject.path.resolve()
        if resolved_subproject == resolved_target:
            continue
        if resolved_target in resolved_subproject.parents:
            exclusions.append(resolved_subproject)
    return exclusions
```

Modify `execute_audit`'s loop (currently lines 167-180) to combine the two exclusion
sources:

```python
    for run in planned_runs(plan, runners):
        run_exclude_paths = plan.exclude_paths + _subproject_exclusions(
            run.target_path, plan.subprojects
        )
        raw = _run_tool_safely(run.runner, run.target_path, run_exclude_paths)
        session.add(
            ToolResult(
                audit_id=audit.id,
                subproject_path=_relative_subproject_path(run.target_path, plan.repository_path),
                tool_name=run.runner.tool_name,
                tool_version=run.runner.tool_version,
                command=raw.command,
                raw_output=raw.raw_output,
                exit_code=raw.exit_code,
                duration_ms=raw.duration_ms,
            )
        )
```

- [ ] **Step 4: Run tests, verify both pass**

Run: `cd radar-audit && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS, all tests in the file including the two new ones and every pre-existing
one (no regression).

- [ ] **Step 5: Commit**

```bash
cd radar-audit
git add src/radar_audit/orchestrator.py tests/test_orchestrator.py
git commit -m "fix(radar-audit): exclude sibling subprojects nested under each run's target path

Modified files:
- radar-audit/src/radar_audit/orchestrator.py — add _subproject_exclusions helper, combine with worktree-based exclude_paths in execute_audit's run loop
- radar-audit/tests/test_orchestrator.py — cover nested-subproject exclusion and colocated-same-path non-exclusion"
```

---

### Task 2: `EslintComplexityRunner` — hardcode `node_modules`/`dist`/`build` exclusion

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/eslint_complexity_runner.py`
- Test: `radar-audit/tests/test_eslint_complexity_runner.py`

**Interfaces:**
- Consumes: nothing new from Task 1 (independent fix — this runner already honors
  whatever `exclude_paths` it's given, Task 1 just ensures it's given the right ones).
- Produces: nothing consumed by other tasks in this plan.

- [ ] **Step 1: Write failing test — build-artifact directory is always excluded, even with no `exclude_paths`**

Add to `radar-audit/tests/test_eslint_complexity_runner.py`, after
`test_excludes_paths_passed_via_exclude_paths`:

```python
@pytest.mark.slow
def test_always_excludes_dist_directory_regardless_of_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "dist/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    assert not any("dist" in f for f in excluded_files)
    assert any("a.js" in f for f in excluded_files)
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_eslint_complexity_runner.py -k dist_directory -v`
Expected: FAIL — `dist/bundle.js`'s high-complexity violation is currently reported
(`assert not any("dist" in f for f in excluded_files)` fails).

- [ ] **Step 3: Add the hardcoded exclusion**

In `radar-audit/src/radar_audit/runners/eslint_complexity_runner.py`, add the constant
near the top (after the existing module-level constants, around line 14):

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "dist", "build")
```

In the `run` method, add the hardcoded `--ignore-pattern` flags right before the existing
`for excluded in exclude_paths:` loop (currently starting at line 45):

```python
            for name in _ALWAYS_EXCLUDED_DIRNAMES:
                command.extend(["--ignore-pattern", f"**/{name}/**"])
            for excluded in exclude_paths:
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `cd radar-audit && uv run pytest tests/test_eslint_complexity_runner.py -v`
Expected: PASS, all tests in the file (this is a `slow`-marked file — real `npx eslint`
runs, allow extra time).

- [ ] **Step 5: Commit**

```bash
cd radar-audit
git add src/radar_audit/runners/eslint_complexity_runner.py tests/test_eslint_complexity_runner.py
git commit -m "fix(radar-audit): hardcode node_modules/dist/build exclusion in EslintComplexityRunner

Modified files:
- radar-audit/src/radar_audit/runners/eslint_complexity_runner.py — add _ALWAYS_EXCLUDED_DIRNAMES, consistent with JscpdRunner/DependencyCruiserRunner
- radar-audit/tests/test_eslint_complexity_runner.py — cover dist/ exclusion independent of exclude_paths"
```

---

### Task 3: `StaticLocRunner` — add `htmlcov` to the always-skipped directory names

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/static_loc_runner.py`
- Test: `radar-audit/tests/test_static_loc_runner.py`

**Interfaces:**
- Consumes: nothing new from Task 1 or 2 (independent fix).
- Produces: nothing consumed by other tasks in this plan.

- [ ] **Step 1: Write failing test — `htmlcov/` directory contents are skipped, but a file merely named `htmlcov...` is not**

Add to `radar-audit/tests/test_static_loc_runner.py`, after
`test_skips_vendor_and_node_modules_directories`:

```python
def test_skips_htmlcov_directory_but_not_files_merely_named_htmlcov(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "line\n",
            "htmlcov/coverage_html_cb_6fb7b396.js": "line one\nline two\n",
            "src/htmlcov_report.js": "line\n",
        },
    )

    runner = StaticLocRunner()
    result = runner.run(repo_path, exclude_paths=[])

    files = result.raw_output["files"]
    assert set(files) == {
        str(repo_path / "src" / "a.js"),
        str(repo_path / "src" / "htmlcov_report.js"),
    }
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_static_loc_runner.py -k htmlcov -v`
Expected: FAIL — `htmlcov/coverage_html_cb_6fb7b396.js` is currently included in `files`
(the assertion's expected set doesn't match the actual set, which also contains the
`htmlcov/` file).

- [ ] **Step 3: Add `htmlcov` to `_SKIP_DIRNAMES`**

In `radar-audit/src/radar_audit/runners/static_loc_runner.py`, line 10:

```python
_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__", "htmlcov"}
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `cd radar-audit && uv run pytest tests/test_static_loc_runner.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Commit**

```bash
cd radar-audit
git add src/radar_audit/runners/static_loc_runner.py tests/test_static_loc_runner.py
git commit -m "fix(radar-audit): skip htmlcov/ generated-artifact directories in StaticLocRunner

Modified files:
- radar-audit/src/radar_audit/runners/static_loc_runner.py — add htmlcov to _SKIP_DIRNAMES
- radar-audit/tests/test_static_loc_runner.py — cover directory-component match, not substring match"
```

---

## After all 3 tasks: whole-branch review, then push + PR

Once all three tasks are committed on `fix/radar-audit-subproject-scope-leaks`:
1. Run the full test suite once: `cd radar-audit && uv run pytest -v` (includes the
   `slow`-marked real-tool tests) — confirm no regressions anywhere else in the suite.
2. Whole-branch review (per `superpowers:subagent-driven-development`'s own end-of-branch
   review step, or a fresh read-through if executed natively).
3. `git push -u origin fix/radar-audit-subproject-scope-leaks` (per
   [[feedback_auto_push]]).
4. Do **not** run `git merge` locally. Provide a ready-to-use PR title/description for the
   user to open manually on GitHub (per the project's PR-over-local-merge convention), and
   do not add a "Generated with Claude Code" or similar footer to it.
5. After the user confirms the PR merged and pulls `main`, this closes out branch 1 of 6
   in the Phase 3 breakdown — update
   `docs/work-in-progress/report-review-battle-plan.md`, `report-review-findings.md`
   (mark findings #9/#3/#8's `htmlcov/` part as fixed), and the
   `project_report_review_battle_plan` / `MEMORY.md` memory files accordingly before
   starting branch 2 (`fix/radar-audit-mypy-cwd-and-severity`).
