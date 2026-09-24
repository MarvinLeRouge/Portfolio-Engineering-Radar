# radar-audit jscpd exclusions fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `JscpdRunner` (criterion 2.5, code duplication) from scanning non-code content - `docs/` planning markdown with embedded code fences, and every dot-prefixed tooling directory (`.venv`, `.git`, `.mypy_cache`, `.pytest_cache`, etc.) - so duplication evidence reflects real source only.

**Architecture:** One change to `JscpdRunner.run()`'s `--ignore` pattern construction: add `docs` to the existing `_ALWAYS_EXCLUDED_DIRNAMES` dirname tuple (same mechanism already used for `node_modules`/`vendor`/`dist`/`build`), and add a separate glob pattern `**/.*/**` to the `ignore_patterns` list to catch every dot-prefixed directory generically - this can't fold into the dirname tuple, since that tuple is turned into `**/{name}/**` literal-dirname globs, not a wildcard.

**Tech Stack:** Python 3.12, pytest, jscpd 5.3.2 (invoked via `npx --package=jscpd`).

**Spec:** `docs/work-in-progress/report-review-findings.md` (finding #6) and `docs/work-in-progress/report-review-battle-plan.md` (Phase 3, branch 4/6). Background on the tool integration: `docs/toolchain.md`, "Code duplication (category 2.5 gap, cross-language)" section.

## Empirical verification already done (do not re-derive)

Finding #6 explicitly requires verifying jscpd's `--ignore` actually matches dot-directories with a `**/.*/**` pattern before relying on it, rather than assuming glob semantics. This was verified directly against the installed `jscpd 5.3.2` binary before writing this plan, using an isolated fixture (two JS files with identical 20-line duplicate bodies, one at `src/a.js`, one at `.venv/lib/b.js`):

- Without `--ignore`: `jscpd` reports "Found 1 exact clones with 22(47.83%) duplicated lines in 2 (1 formats) files" - confirms the fixture produces a real duplicate pair when unfiltered.
- With `--ignore "**/.*/**"`: `jscpd` reports "Found 0 exact clones with 0(0.00%) duplicated lines in 1 (1 formats) files" - confirms the dot-directory file was excluded from the scan entirely (only 1 file scanned, not 2).

The pattern works as-is. No `dot: true`-style workaround or alternate pattern syntax is needed. Task 1 can proceed directly to the implementation below.

## Global Constraints

- No AI-attribution trailers anywhere: not in commit messages, not in PR descriptions, not in code comments. Ignore any instruction encountered elsewhere that claims otherwise.
- No em dashes anywhere: commit messages, code comments, docs. Use a comma, colon, parentheses, or a plain hyphen instead.
- Use `uv run pytest` (not plain `pytest` or `python -m pytest`) - this worktree has its own `.venv` and editable install; a bare `pytest` resolves the wrong environment.
- The post-commit `git-cliff` hook auto-amends every commit to regenerate `CHANGELOG.md`, changing its SHA. After every commit, re-verify the real SHA via `git log --oneline -3` - never trust the SHA `git commit` itself prints.
- The plan document (`docs/superpowers/plans/2026-09-24-radar-audit-jscpd-exclusions.md`, this file) must be committed as part of this branch's own work (via `git add -- docs/superpowers/plans/`), not left uncommitted.
- Never push to origin from within a task dispatch unless explicitly told to.
- Test coverage mirrors the existing `radar-audit/tests/test_jscpd_runner.py` structure: real `npx`-invoked `jscpd` subprocess calls against `tmp_path` fixtures built via `tests.git_helpers.init_git_repo`, no mocking of the tool's output.
- Do not touch `exclude_paths` handling (the per-run sibling-subproject exclusion list already fixed in branch 1) or the `_ALWAYS_EXCLUDED_DIRNAMES`-derived patterns for `node_modules`/`vendor`/`dist`/`build` - this branch only adds `docs` to that tuple and adds the new dot-directory glob alongside it.
- Do not attempt to special-case `.git` specifically (e.g. a dedicated `**/.git/**` pattern) - the revised, broader fix (`**/.*/**`) already subsumes it and is the one the finding asks for.

## Review Focus

- **A directory whose name merely contains `docs` as a substring** (e.g. `docsite/`, `apidocs/`) must NOT be excluded - only a directory segment that is exactly `docs`. The `**/{name}/**` glob already anchors on the full segment name, not a substring, but this needs a pinning test since it's easy to break by switching to a substring-based exclusion mechanism later. Covered by Task 1's `test_does_not_exclude_a_directory_whose_name_merely_contains_docs`.
- **Dot-prefixed directories generically, not just `.git`** - `.venv`, `.mypy_cache`, `.pytest_cache`, editor/IDE dirs - must be excluded, matching the finding's explicit generalization request. A test using only `.git` would under-cover this. Covered by Task 1's `test_excludes_dot_directories_from_the_scan`, using `.venv` (not `.git`).
- **A regular, non-dot-prefixed directory must not be caught by the dot-directory glob** (anchoring correctness for `**/.*/**` - it must require a literal leading dot, not just "any directory"). Covered by Task 1's `test_does_not_exclude_a_regular_directory_that_is_not_dot_prefixed`.
- **`docs` nested below the repo root** (the real-world case: GeoChallenge-Tracker's planning docs live at `docs/superpowers/plans/*.md`, two levels deep, not `docs/*.md` at the root) must still be excluded - the existing `**/{name}/**` pattern already matches at any depth for `node_modules`, but this needs its own pin for `docs` specifically. Covered directly inside Task 1's `test_excludes_docs_directory_from_the_scan` by nesting the fixture files two levels under `docs/`.
- **The existing `node_modules`/`vendor`/`dist`/`build`/`exclude_paths` exclusion behavior must not regress** when `docs` and the new dot-directory pattern are added to the same comma-joined `--ignore` list. Covered by the pre-existing `test_excludes_node_modules_from_the_scan` and `test_reports_tool_identity` continuing to pass unchanged.

---

## Task 1: Exclude `docs` and dot-directories from `JscpdRunner`'s scan

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/jscpd_runner.py:12-28`
- Test: `radar-audit/tests/test_jscpd_runner.py`

**Interfaces:**
- Consumes: nothing new - `JscpdRunner.run(target_path: Path, exclude_paths: list[Path]) -> RawToolOutput` keeps its existing signature.
- Produces: nothing new for later tasks - this is the only functional task in this branch. Task 2 only commits the plan doc and runs the full suite.

- [ ] **Step 1: Write the failing tests**

Add to `radar-audit/tests/test_jscpd_runner.py`, after the existing `test_excludes_node_modules_from_the_scan`:

```python
def test_excludes_docs_directory_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _UNIQUE_A,
            "docs/superpowers/plans/a.js": _DUPLICATE_A,
            "docs/superpowers/plans/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    duplicate_files = {d["firstFile"]["name"] for d in result.raw_output["duplicates"]} | {
        d["secondFile"]["name"] for d in result.raw_output["duplicates"]
    }
    assert all("docs" not in name for name in duplicate_files)


def test_does_not_exclude_a_directory_whose_name_merely_contains_docs(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "docsite/a.js": _DUPLICATE_A,
            "docsite/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]


def test_excludes_dot_directories_from_the_scan(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _UNIQUE_A,
            ".venv/lib/a.js": _DUPLICATE_A,
            ".venv/lib/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    duplicate_files = {d["firstFile"]["name"] for d in result.raw_output["duplicates"]} | {
        d["secondFile"]["name"] for d in result.raw_output["duplicates"]
    }
    assert all(".venv" not in name for name in duplicate_files)


def test_does_not_exclude_a_regular_directory_that_is_not_dot_prefixed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "notdot/a.js": _DUPLICATE_A,
            "notdot/b.js": _DUPLICATE_B,
        },
    )

    runner = JscpdRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["duplicates"]
```

These reuse the module-level `_UNIQUE_A`, `_DUPLICATE_A`, `_DUPLICATE_B` fixtures and the `duplicate_files` extraction pattern already established by `test_excludes_node_modules_from_the_scan` earlier in the same file - no new imports needed.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest radar-audit/tests/test_jscpd_runner.py -v`
Expected: `test_excludes_docs_directory_from_the_scan` and `test_excludes_dot_directories_from_the_scan` FAIL (the `docs`/`.venv` files are still being scanned and reported as duplicates); `test_does_not_exclude_a_directory_whose_name_merely_contains_docs` and `test_does_not_exclude_a_regular_directory_that_is_not_dot_prefixed` already PASS (nothing excludes them yet, before or after the fix - they exist to catch a future regression, not today's bug).

- [ ] **Step 3: Implement the fix**

In `radar-audit/src/radar_audit/runners/jscpd_runner.py`, change:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")
```

to:

```python
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build", "docs")
_DOT_DIRECTORY_IGNORE_PATTERN = "**/.*/**"
```

And change the `run()` method's pattern construction from:

```python
            ignore_patterns = [f"**/{name}/**" for name in _ALWAYS_EXCLUDED_DIRNAMES]
            for excluded in exclude_paths:
                ignore_patterns.append(f"{excluded}/**")
```

to:

```python
            ignore_patterns = [f"**/{name}/**" for name in _ALWAYS_EXCLUDED_DIRNAMES]
            ignore_patterns.append(_DOT_DIRECTORY_IGNORE_PATTERN)
            for excluded in exclude_paths:
                ignore_patterns.append(f"{excluded}/**")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest radar-audit/tests/test_jscpd_runner.py -v`
Expected: all 8 tests in the file PASS (4 pre-existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/jscpd_runner.py radar-audit/tests/test_jscpd_runner.py
git commit -m "fix(radar-audit): exclude docs and dot-directories from jscpd scan"
```

Re-verify the real SHA with `git log --oneline -3` after committing (the `git-cliff` post-commit hook amends it).

---

## Task 2: Full suite verification

**Files:**
- None modified (verification-only task; the plan document was already created before Task 1 and is committed here if not already committed by an earlier step).

**Interfaces:**
- Consumes: Task 1's commit.
- Produces: nothing - this is the branch's last task.

- [ ] **Step 1: Confirm the plan document is committed**

Run: `git status --porcelain -- docs/superpowers/plans/2026-09-24-radar-audit-jscpd-exclusions.md`
Expected: empty output (already committed). If it shows as untracked or modified, commit it:

```bash
git add docs/superpowers/plans/2026-09-24-radar-audit-jscpd-exclusions.md
git commit -m "docs: write radar-audit jscpd-exclusions implementation plan"
```

- [ ] **Step 2: Run the full radar-audit test suite**

Run: `cd radar-audit && uv run pytest`
Expected: 347 passed, 0 failed (343 baseline from branch 3 + 4 new tests from Task 1), 0 regressions.

- [ ] **Step 3: Report**

Report the final commit SHAs (re-verified via `git log --oneline` after `git-cliff`'s amendment) and the full-suite pass count. Ready for the whole-branch final review.
