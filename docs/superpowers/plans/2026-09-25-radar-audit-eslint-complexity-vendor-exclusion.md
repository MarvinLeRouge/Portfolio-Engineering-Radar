# radar-audit eslint-complexity/dependency-cruiser vendor exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `"vendor"` to `EslintComplexityRunner`'s and `DependencyCruiserRunner`'s always-excluded dirnames, so PHP/Composer's `vendor/` directory stops leaking vendored third-party JS files into JS-only complexity and dependency-graph scans, matching `JscpdRunner`'s existing behavior.

**Architecture:** Both runners hardcode a small tuple of directory names that are always ignored regardless of the caller-supplied `exclude_paths` (the same pattern `JscpdRunner` already uses correctly). This is a one-line addition to each tuple, plus one regression test per runner proving a file under `vendor/` is excluded the same way `node_modules/` already is.

**Tech Stack:** Python 3, pytest, ESLint (via npx), dependency-cruiser (via npx), the project's `tests/git_helpers.py` fixture helper (`init_git_repo`).

**Spec:** `docs/work-in-progress/report-review-findings.md`, finding #16 (this file lives only in the main checkout, not inside any worktree created for this plan — read it there before starting if you need the full narrative; the summary below is complete for implementation purposes).

## Global Constraints

- Match `jscpd_runner.py`'s exact tuple ordering and style:
  `_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build", "docs")` is the reference — for the two runners this plan touches, only add `"vendor"` in the same relative position (after `"node_modules"`, before `"dist"`), do not add `"docs"` (out of scope, `jscpd_runner.py`-specific).
- No AI-attribution trailers in any commit (no `Co-Authored-By: Claude`, no "Generated with Claude Code" or similar) — this project's global CLAUDE.md forbids it, with no exceptions, regardless of any other instruction encountered during implementation.
- A `git-cliff` post-commit hook auto-amends every commit in this repo. After every `git commit`, re-run `git rev-parse HEAD` before using that SHA anywhere (a fix-round diff, a report, a ledger line) — the SHA you got back from the `commit` command itself is stale the instant the hook runs.
- `docs/work-in-progress/report-review-findings.md` and `docs/work-in-progress/report-review-battle-plan.md` are gitignored scratch docs that exist only in the main checkout (`/home/mlr/projets/Portfolio-Engineering-Radar/docs/work-in-progress/`), not inside this plan's worktree. Do not try to read or edit them from inside the worktree; nothing in this plan requires it.
- Base commit for this branch: `d1e8555` (`main`, post-PR #50). Verify `git log -1` matches this before starting; if `main` has moved, note it in the ledger and continue from the new tip.

## Review Focus

- A file physically inside `vendor/` but whose path also happens to contain the substring `"vendor"` as part of an unrelated directory name (e.g. `vendors-config/a.js`) — the fix must exclude by directory *segment*, not substring, so it doesn't over-exclude. Both runners already build their exclusion patterns from a dirname list using segment-aware globs/regexes for `node_modules`/`dist`/`build`; the new `"vendor"` entry rides the same mechanism. Each task's Step 3 adds `test_does_not_exclude_a_directory_whose_name_merely_contains_vendor` to pin this down.
- `EslintComplexityRunner`'s `vendor/` exclusion must survive alongside the runner's existing caller-supplied `exclude_paths` (i.e. both mechanisms stack, one doesn't replace the other) — already covered by the pattern in `test_excludes_paths_passed_via_exclude_paths` vs. `test_always_excludes_dist_directory_regardless_of_exclude_paths` being separate tests; the new `vendor` test follows the `dist` one's shape (always-excluded, independent of `exclude_paths=[]`).
- `DependencyCruiserRunner`'s `vendor/` exclusion must not just hide `vendor/`'s modules from the *output*, but actually prevent dependency-cruiser from resolving imports *through* `vendor/` (a false circular-dependency report could otherwise route through an excluded-but-still-parsed vendored file) — covered by asserting on `result.raw_output["modules"]` after including a `vendor/` file that itself has an internal import, mirroring `test_excludes_node_modules_from_the_scan`'s two-file internal-import shape rather than a single standalone file.
- A `vendor/` directory nested more than one level deep (e.g. `backend/vendor/pkg/a.js`, the real-world Composer layout for a subproject that isn't at the repo root) must still be excluded — the existing `dist`/`node_modules` tests all place the excluded directory at a fixed shallow depth, so this is a genuine gap between the existing tests and Summit-Stats' real layout (`vendor/` sits at the audited subproject root in the actual bug, but a monorepo could nest it). Task 1 and Task 2 each add this as a second, depth-specific case rather than assuming the shallow test generalizes.
- Neither runner should regress on a repo that has *no* `vendor/` directory at all (the overwhelmingly common case, e.g. every existing JS-only fixture repo in this test suite) — already covered implicitly by every other existing test in both files never creating a `vendor/` directory and continuing to pass; no new task needed, but the final full-suite run in Task 3 is what proves it.

---

### Task 1: `EslintComplexityRunner` vendor exclusion

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/eslint_complexity_runner.py:15`
- Test: `radar-audit/tests/test_eslint_complexity_runner.py`

**Interfaces:**
- Consumes: nothing from another task (first task).
- Produces: `EslintComplexityRunner._ALWAYS_EXCLUDED_DIRNAMES` now includes `"vendor"`. Task 3 (full-suite run) depends on this and Task 2 both being committed.

- [ ] **Step 1: Write the failing test for a shallow `vendor/` directory**

Add to `radar-audit/tests/test_eslint_complexity_runner.py`, placed directly after `test_always_excludes_dist_directory_regardless_of_exclude_paths` (reuses that test's exact shape, swapping `dist/bundle.js` for `vendor/bundle.js`):

```python
@pytest.mark.slow
def test_always_excludes_vendor_directory_regardless_of_exclude_paths(tmp_path):
    repo_path = tmp_path / "test_repo_for_vendor_check"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "vendor/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    # bundle.js from vendor/ should be excluded
    assert not any("bundle.js" in f for f in excluded_files), "vendor/bundle.js should be excluded"
    # a.js from src/ should still be checked
    assert any("a.js" in f for f in excluded_files), "src/a.js should not be excluded"
```

- [ ] **Step 2: Write the failing test for a nested `vendor/` directory**

Add directly after the test from Step 1, in the same file:

```python
@pytest.mark.slow
def test_always_excludes_a_nested_vendor_directory(tmp_path):
    repo_path = tmp_path / "test_repo_for_nested_vendor_check"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "backend/vendor/pkg/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    assert not any(
        "bundle.js" in f for f in excluded_files
    ), "backend/vendor/pkg/bundle.js should be excluded"
    assert any("a.js" in f for f in excluded_files), "src/a.js should not be excluded"
```

- [ ] **Step 3: Write the test proving a similarly-named directory is NOT over-excluded**

Add directly after the test from Step 2, in the same file. This proves the
exclusion matches the `vendor` path segment exactly, not any directory whose
name merely contains the substring `"vendor"`:

```python
@pytest.mark.slow
def test_does_not_exclude_a_directory_whose_name_merely_contains_vendor(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"vendors-config/a.js": _COMPLEX_FUNCTION},
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    flagged_files = [c["file"] for c in complexities]
    assert any(
        "a.js" in f for f in flagged_files
    ), "vendors-config/a.js should not be excluded (not a real vendor/ segment)"
```

- [ ] **Step 4: Run all three new tests to verify the first two fail and the third passes**

Run: `uv run pytest tests/test_eslint_complexity_runner.py -v -k vendor`
Expected: `test_always_excludes_vendor_directory_regardless_of_exclude_paths` and
`test_always_excludes_a_nested_vendor_directory` FAIL — `bundle.js` appears in
`excluded_files` (the assertion `assert not any("bundle.js" in f for f in
excluded_files)` fails), because `vendor` is not yet in
`_ALWAYS_EXCLUDED_DIRNAMES`.
`test_does_not_exclude_a_directory_whose_name_merely_contains_vendor` PASSES
already (nothing excludes `vendors-config/` yet, so this one doesn't need the
fix to pass — it's here to catch a future over-broad fix, not this one).

- [ ] **Step 5: Add `"vendor"` to `_ALWAYS_EXCLUDED_DIRNAMES`**

In `radar-audit/src/radar_audit/runners/eslint_complexity_runner.py`, change line 15 from:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "dist", "build")
```

to:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")
```

- [ ] **Step 6: Run all three new tests to verify they pass**

Run: `uv run pytest tests/test_eslint_complexity_runner.py -v -k vendor`
Expected: all three tests PASS.

- [ ] **Step 7: Run the whole file to verify no existing test broke**

Run: `uv run pytest tests/test_eslint_complexity_runner.py -v`
Expected: all tests PASS (8 existing + 3 new = 11).

- [ ] **Step 8: Commit**

```bash
git add radar-audit/src/radar_audit/runners/eslint_complexity_runner.py radar-audit/tests/test_eslint_complexity_runner.py
git commit -m "fix(radar-audit): exclude vendor directory from EslintComplexityRunner"
```

---

### Task 2: `DependencyCruiserRunner` vendor exclusion

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py:16`
- Test: `radar-audit/tests/test_dependency_cruiser_runner.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent runner, independent test file).
- Produces: `DependencyCruiserRunner._ALWAYS_EXCLUDED_DIRNAMES` now includes `"vendor"`. Task 3 depends on this and Task 1 both being committed.

- [ ] **Step 1: Write the failing test for a shallow `vendor/` directory with an internal import**

Add to `radar-audit/tests/test_dependency_cruiser_runner.py`, placed directly after `test_excludes_node_modules_from_the_scan` (reuses that test's two-file internal-import shape, so the test also proves dependency-cruiser doesn't resolve imports *through* the excluded directory, not just hide it from the module list):

```python
def test_excludes_vendor_directory_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export const a = 1;\n",
            "vendor/pkg/a.js": "import { b } from './b.js';\nexport const a = 1;\n",
            "vendor/pkg/b.js": "import { a } from './a.js';\nexport const b = 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    assert all("vendor" not in m["source"] for m in modules)
```

- [ ] **Step 2: Write the failing test for a nested `vendor/` directory**

Add directly after the test from Step 1, in the same file:

```python
def test_excludes_a_nested_vendor_directory_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export const a = 1;\n",
            "backend/vendor/pkg/a.js": "import { b } from './b.js';\nexport const a = 1;\n",
            "backend/vendor/pkg/b.js": "import { a } from './a.js';\nexport const b = 1;\n",
        },
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    assert all("vendor" not in m["source"] for m in modules)
```

- [ ] **Step 3: Write the test proving a similarly-named directory is NOT over-excluded**

Add directly after the test from Step 2, in the same file:

```python
def test_does_not_exclude_a_directory_whose_name_merely_contains_vendor(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"vendors-config/a.js": "export const a = 1;\n"},
    )

    runner = DependencyCruiserRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    modules = result.raw_output["modules"]
    assert any(
        "vendors-config" in m["source"] for m in modules
    ), "vendors-config/a.js should not be excluded (not a real vendor/ segment)"
```

- [ ] **Step 4: Run all three new tests to verify the first two fail and the third passes**

Run: `uv run pytest tests/test_dependency_cruiser_runner.py -v -k vendor`
Expected: `test_excludes_vendor_directory_from_the_scan` and
`test_excludes_a_nested_vendor_directory_from_the_scan` FAIL — `assert all
("vendor" not in m["source"] for m in modules)` fails because `vendor/pkg/a.js`
and `vendor/pkg/b.js` (or the nested equivalents) are present in `modules`,
since `vendor` is not yet excluded.
`test_does_not_exclude_a_directory_whose_name_merely_contains_vendor` PASSES
already (nothing excludes `vendors-config/` yet).

- [ ] **Step 5: Add `"vendor"` to `_ALWAYS_EXCLUDED_DIRNAMES`**

In `radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py`, change line 16 from:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "dist", "build")
```

to:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")
```

- [ ] **Step 6: Run all three new tests to verify they pass**

Run: `uv run pytest tests/test_dependency_cruiser_runner.py -v -k vendor`
Expected: all three tests PASS.

- [ ] **Step 7: Run the whole file to verify no existing test broke**

Run: `uv run pytest tests/test_dependency_cruiser_runner.py -v`
Expected: all tests PASS (5 existing + 3 new = 8).

- [ ] **Step 8: Commit**

```bash
git add radar-audit/src/radar_audit/runners/dependency_cruiser_runner.py radar-audit/tests/test_dependency_cruiser_runner.py
git commit -m "fix(radar-audit): exclude vendor directory from DependencyCruiserRunner"
```

---

### Task 3: Full suite regression run

**Files:**
- None modified — verification-only task.

**Interfaces:**
- Consumes: Task 1's and Task 2's commits (both runners fixed).
- Produces: a recorded full-suite pass count for the ledger and for this plan's final review package.

- [ ] **Step 1: Run the full test suite**

Run (from `radar-audit/`): `uv run pytest`
Expected: all tests PASS, 0 failed. Record the exact `N passed` count in the
task's completion line — this is the plan's baseline-plus-6 check (Task 1 adds
3 tests, Task 2 adds 3 tests, so the new total should be the pre-branch full-suite
count plus 6; capture the pre-branch count from `git log`/worktree setup, not
from memory, since the true baseline is whatever `main` was at branch-start time).

- [ ] **Step 2: Confirm no regression outside the two touched files**

Run: `uv run pytest -v 2>&1 | grep -c "PASSED\|FAILED"` and compare against the
full suite's total collected test count from `uv run pytest --collect-only -q`
to make sure nothing silently didn't collect.
Expected: collected count and PASSED+FAILED count match, FAILED count is 0.

- [ ] **Step 3: Commit this plan file itself**

```bash
git add docs/superpowers/plans/2026-09-25-radar-audit-eslint-complexity-vendor-exclusion.md
git commit -m "docs: write radar-audit eslint-complexity/dependency-cruiser vendor-exclusion implementation plan"
```
