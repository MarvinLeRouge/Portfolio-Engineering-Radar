# Dependency-Audit Lockfile Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `PnpmAuditRunner` detect which lockfile a JS subproject actually uses (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`) and dispatch to the matching audit tool (`npm audit`, `pnpm audit`, `yarn audit`), instead of always running `pnpm audit` and silently producing no CVE findings for npm- or yarn-based subprojects.

**Architecture:** `PnpmAuditRunner.run()` gains a lockfile-detection step (`_LOCKFILE_COMMANDS`, an ordered dict mapping lockfile filename to the command that audits it) before the existing subprocess-and-parse logic. Each of the three tools' JSON output is normalized by its own small static parser method into the same `{"id", "package", "severity", "fix_available"}` list shape the normalizer already consumes; the existing `_SEVERITY_MAP` and `_failed()` failure-shape helper are reused unchanged across all three paths.

**Tech Stack:** Python 3, pytest, `subprocess`, real `npm`/`pnpm` binaries plus `npx --package=yarn -- yarn` for yarn (yarn classic is not guaranteed to be globally installed in the dev/CI environment, unlike npm and pnpm).

**Spec:** `docs/work-in-progress/report-review-findings.md`, finding #2, in the main checkout (this file is gitignored scratch and not present in this worktree - its relevant content is reproduced below so this plan is self-contained):

> ## 2. `PnpmAuditRunner` runs `pnpm audit` unconditionally, even on npm projects
> - **File:** `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py:39`
> - **Real, confirmed impact:** GeoChallenge-Tracker's JS dependencies are never scanned for CVEs by any tool, because the subproject uses npm (`package-lock.json`) but this runner always shells out to `pnpm audit`, which fails immediately (no `pnpm-lock.yaml`). A real `npm audit --json` against the same dependencies finds HIGH severity advisories.
> - **Compounding, separate limitation:** `PipAuditRunner` hardcodes `severity: "MEDIUM"` for every finding (`pip_audit_runner.py:78`) - kept as a lower-priority follow-up, explicitly NOT part of this branch's required fix batch.
> - **Suggested fix:** run `npm audit` (or detect the lockfile type and dispatch to the matching audit tool: `npm audit` for `package-lock.json`, `pnpm audit` for `pnpm-lock.yaml`, `yarn audit` for `yarn.lock`) instead of assuming pnpm unconditionally.
> - **Status:** dispositioned 2026-09-24: fix now (lockfile-type dispatch), Phase 3. Severity-sourcing note kept as a lower-priority follow-up, not part of the required fix batch.

## Global Constraints

- Keep the class name (`PnpmAuditRunner`), file name (`pnpm_audit_runner.py`), and `tool_name = "pnpm-audit"` class attribute unchanged. Do not touch `cli.py`'s import/registration of this runner or `dependency_vulnerabilities.py`'s `_RELEVANT_TOOLS = {"pip-audit", "pnpm-audit", "composer-audit"}` set - neither needs a change under this design, and renaming would ripple into both files for no functional benefit. The `command` field on every `RawToolOutput` this runner produces always records the real command that ran (e.g. `"npm audit --json"`), so the actual tool used stays fully inspectable in stored data even though the class/tool identifier stays generic.
- The `PipAuditRunner` flat-`"MEDIUM"`-severity limitation noted in the spec excerpt above is explicitly OUT of scope for this branch. Do not touch `pip_audit_runner.py`.
- yarn is dispatched via `["npx", "--package=yarn", "--", "yarn", "audit", "--json"]`, never a bare `yarn` binary - this matches the existing `JscpdRunner`'s `["npx", "--package=jscpd", "--", "jscpd", ...]` convention (no `--yes` flag) and avoids requiring a global yarn install, since yarn is not present as a global binary in the dev/CI environment while `npm` and `pnpm` are.
- Severity strings from all three tools (`critical`/`high`/`moderate`/`low`/`info`, always lowercase) map through the existing `_SEVERITY_MAP` dict unchanged - confirmed empirically identical across npm, pnpm, and yarn, since all three ultimately draw from the same upstream npm/GHSA advisory database.
- When more than one lockfile is present in the same directory, detection priority is npm first, then pnpm, then yarn (an arbitrary but deterministic, documented choice - not left to dict-iteration chance).

## Review Focus

- **A subproject with `package.json` but no recognized lockfile at all** (a stub committed before anyone ever ran an install) - the runner must report a clear, structured failure (`NO_LOCKFILE_DETECTED`) without ever shelling out to any audit tool, rather than crashing or silently reporting zero vulnerabilities as if the subproject were clean. Covered by Task 1's `test_reports_a_failed_audit_when_no_supported_lockfile_is_present`.
- **A yarn audit run that errors before producing a trailing `auditSummary` line** (e.g. a corrupted or unparseable `yarn.lock`) - the parser must treat this as a failed audit, not silently report zero vulnerabilities as if the project were clean. Covered by Task 2's `test_yarn_parser_returns_none_when_no_summary_line_is_reached`.
- **npm's `via` array mixing string entries (cross-references to another vulnerable dependency) with dict entries (real advisories)** - the parser must skip the string entries without crashing or fabricating a bogus advisory from one. Covered by Task 1's `test_npm_parser_skips_transitive_via_string_entries`.
- **Multiple lockfiles coexisting in the same directory** (e.g. a repo mid-migration between package managers) - detection must give a deterministic, documented result (npm wins) rather than depending on filesystem iteration order. Covered by Task 1's `test_prefers_npm_lockfile_when_multiple_lockfiles_are_present`.
- **`fix_available` normalization when no fix exists** (npm's `fixAvailable: false` vs. pnpm/yarn's `patched_versions: "<0.0.0"` placeholder-for-no-fix convention) - the flag must come out `False` under both shapes rather than defaulting to a wrong truthy value. Covered by Task 1's `test_npm_parser_reports_no_fix_available_when_fixavailable_is_false` (npm) and the existing, unmodified pnpm test already exercises the pnpm/yarn-shared `patched_versions` convention on the vulnerable-pin case.

---

### Task 1: Lockfile detection + npm dispatch, pnpm parsing extracted

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py` (full rewrite of the module)
- Test: `radar-audit/tests/test_pnpm_audit_runner.py`

**Interfaces:**
- Consumes: `radar_audit.runner.RawToolOutput` (existing, unchanged: `command: str`, `raw_output: dict`, `exit_code: int`, `duration_ms: int`).
- Produces: `PnpmAuditRunner._detect_lockfile(target_path: Path) -> str | None` (returns one of `"package-lock.json"`, `"pnpm-lock.yaml"`, `"yarn.lock"`, or `None`). `PnpmAuditRunner._parse_npm_audit(stdout: str) -> list[dict] | None` (static method, `None` means "failed to parse / not a successful audit"). `PnpmAuditRunner._parse_pnpm_audit(stdout: str) -> list[dict] | None` (static method; same contract, replaces the old inline logic in `run()`). Task 2 consumes both this method-naming pattern and the `_LOCKFILE_COMMANDS` / `_PARSER_NAMES` dicts to add its own `yarn.lock` entry and `_parse_yarn_audit` method.

- [ ] **Step 1: Write the failing tests for npm dispatch, lockfile priority, and the two npm-parser edge cases**

Open `radar-audit/tests/test_pnpm_audit_runner.py`. The file already imports `json` and `subprocess` at the top - no new imports are needed. Add this helper near the top, next to the existing `_pnpm_install` helper:

```python
def _npm_install(repo_path):
    subprocess.run(
        ["npm", "install", "--package-lock-only"], cwd=repo_path, check=True
    )
```

Add these test functions to the file:

```python
def test_dispatches_to_npm_audit_when_package_lock_json_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps(
                {"name": "npm-dispatch-test", "dependencies": {"lodash": "4.17.15"}}
            )
        },
    )
    _npm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.command.startswith("npm audit")
    assert result.raw_output["manifest_found"] is True
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert len(vulnerabilities) > 0
    assert all(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_prefers_npm_lockfile_when_multiple_lockfiles_are_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps({"name": "multi-lock-test", "dependencies": {}})
        },
    )
    _npm_install(repo_path)
    (repo_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.command.startswith("npm audit")


def test_reports_a_failed_audit_when_no_supported_lockfile_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": json.dumps({"name": "no-lock-test", "dependencies": {}})},
    )

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["error"]["code"] == "NO_LOCKFILE_DETECTED"
    assert "vulnerabilities" not in result.raw_output


def test_npm_parser_skips_transitive_via_string_entries():
    stdout = json.dumps(
        {
            "vulnerabilities": {
                "lodash": {
                    "via": [
                        {"source": 1106913, "name": "lodash", "severity": "high"}
                    ],
                    "fixAvailable": {"name": "lodash", "version": "4.18.1"},
                },
                "some-wrapper": {
                    "via": ["lodash"],
                    "fixAvailable": False,
                },
            }
        }
    )

    vulnerabilities = PnpmAuditRunner._parse_npm_audit(stdout)

    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]["package"] == "lodash"
    assert vulnerabilities[0]["id"] == "1106913"
    assert vulnerabilities[0]["severity"] == "HIGH"


def test_npm_parser_reports_no_fix_available_when_fixavailable_is_false():
    stdout = json.dumps(
        {
            "vulnerabilities": {
                "lodash": {
                    "via": [{"source": 1106913, "name": "lodash", "severity": "high"}],
                    "fixAvailable": False,
                }
            }
        }
    )

    vulnerabilities = PnpmAuditRunner._parse_npm_audit(stdout)

    assert vulnerabilities[0]["fix_available"] is False
```

Now find the existing test named `test_reports_a_failed_audit_when_there_is_no_lockfile` in this same file and **delete it entirely** - it is superseded by the new `test_reports_a_failed_audit_when_no_supported_lockfile_is_present` above, which covers the same scenario (`package.json` present, no lockfile created) under the new, more accurate behavior (detection happens before any subprocess call, so the synthetic error code changes from pnpm's own `ERR_PNPM_AUDIT_NO_LOCKFILE` to this runner's own `NO_LOCKFILE_DETECTED`).

- [ ] **Step 2: Run the new/changed tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v`
Expected: the 4 new tests fail (`test_dispatches_to_npm_audit_when_package_lock_json_is_present`, `test_prefers_npm_lockfile_when_multiple_lockfiles_are_present`, `test_npm_parser_skips_transitive_via_string_entries`, `test_npm_parser_reports_no_fix_available_when_fixavailable_is_false`) with `AttributeError: type object 'PnpmAuditRunner' has no attribute '_parse_npm_audit'` or an assertion failure (npm audit is never invoked by the old code); `test_reports_a_failed_audit_when_no_supported_lockfile_is_present` fails with a `KeyError` or assertion mismatch since the old code always runs `pnpm audit` and reports `ERR_PNPM_AUDIT_NO_LOCKFILE`, not `NO_LOCKFILE_DETECTED`. The 3 remaining original tests (`test_reports_no_manifest`, `test_reports_no_vulnerabilities_on_empty_dependencies`, `test_reports_vulnerabilities_on_a_known_vulnerable_pin`, `test_reports_tool_identity`) still pass.

- [ ] **Step 3: Rewrite `pnpm_audit_runner.py` with lockfile detection, npm dispatch, and pnpm parsing extracted into its own method**

Replace the full contents of `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py` with:

```python
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "moderate": "MEDIUM",
    "low": "LOW",
    "info": "LOW",
}

# Priority order when a target directory somehow carries more than one
# lockfile: npm first (most universal), then pnpm, then yarn. This dict is
# also the source of truth for which lockfile filenames are recognized at
# all -- _detect_lockfile walks its keys in this order.
_LOCKFILE_COMMANDS: dict[str, list[str]] = {
    "package-lock.json": ["npm", "audit", "--json"],
    "pnpm-lock.yaml": ["pnpm", "audit", "--json"],
    # yarn is dispatched through npx (like JscpdRunner's jscpd) rather than a
    # bare `yarn` binary, since yarn classic is not guaranteed to be globally
    # installed the way npm (ships with Node) and pnpm (assumed present,
    # matching this runner's pre-existing pnpm-audit convention) are.
    "yarn.lock": ["npx", "--package=yarn", "--", "yarn", "audit", "--json"],
}

_PARSER_NAMES: dict[str, str] = {
    "package-lock.json": "_parse_npm_audit",
    "pnpm-lock.yaml": "_parse_pnpm_audit",
    "yarn.lock": "_parse_yarn_audit",
}


class PnpmAuditRunner:
    """Runs the JS dependency-audit tool matching the subproject's lockfile
    (npm audit / pnpm audit / yarn audit) for criterion 4.1.

    Despite the class name (kept to minimize the change's footprint on
    cli.py's registration and the dependency_vulnerabilities normalizer's
    pnpm-audit tool_name key), this runner audits any JS subproject
    regardless of package manager: it detects which lockfile is present
    and dispatches to the matching command. The raw `command` field on
    every result always records the real command that ran.
    """

    tool_name = "pnpm-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "package.json"
        if not manifest.exists():
            return RawToolOutput(
                command="npm/pnpm/yarn audit (skipped, no package.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        lockfile_name = self._detect_lockfile(target_path)
        if lockfile_name is None:
            return RawToolOutput(
                command="npm/pnpm/yarn audit (skipped, no lockfile)",
                raw_output={
                    "manifest_found": True,
                    "error": {
                        "code": "NO_LOCKFILE_DETECTED",
                        "summary": "None of package-lock.json, pnpm-lock.yaml, "
                        "yarn.lock found in the target directory.",
                    },
                },
                exit_code=0,
                duration_ms=0,
            )

        command = _LOCKFILE_COMMANDS[lockfile_name]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        parser = getattr(self, _PARSER_NAMES[lockfile_name])
        vulnerabilities = parser(completed.stdout)
        if vulnerabilities is None:
            return self._failed(command, completed, duration_ms)

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _detect_lockfile(target_path: Path) -> str | None:
        for lockfile_name in _LOCKFILE_COMMANDS:
            if (target_path / lockfile_name).exists():
                return lockfile_name
        return None

    @staticmethod
    def _parse_npm_audit(stdout: str) -> list[dict[str, object]] | None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        if (
            not isinstance(data, dict)
            or "error" in data
            or not isinstance(data.get("vulnerabilities"), dict)
        ):
            return None

        vulnerabilities = []
        for package_name, entry in data["vulnerabilities"].items():
            for via in entry.get("via", []):
                # A string `via` entry just names another vulnerable
                # dependency this package pulls in; the real advisory is
                # reported under that dependency's own top-level entry, so
                # string entries are skipped here to avoid double-counting
                # or fabricating a malformed advisory from a bare name.
                if not isinstance(via, dict):
                    continue
                vulnerabilities.append(
                    {
                        "id": str(via["source"]),
                        "package": package_name,
                        "severity": _SEVERITY_MAP.get(via.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(entry.get("fixAvailable")),
                    }
                )
        return vulnerabilities

    @staticmethod
    def _parse_pnpm_audit(stdout: str) -> list[dict[str, object]] | None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        # pnpm reports its own failures as valid JSON with a top-level "error" key
        # (e.g. ERR_PNPM_AUDIT_NO_LOCKFILE, registry errors), confirmed empirically.
        # pnpm's success JSON always uses an object keyed by advisory id (including the
        # zero-dependency case -- `{}`, not `[]`), so anything else is a failed audit.
        if (
            not isinstance(data, dict)
            or "error" in data
            or not isinstance(data.get("advisories"), dict)
        ):
            return None

        vulnerabilities = []
        for advisory in data["advisories"].values():
            patched = advisory.get("patched_versions")
            vulnerabilities.append(
                {
                    "id": str(advisory["id"]),
                    "package": advisory["module_name"],
                    "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                    "fix_available": bool(patched) and patched != "<0.0.0",
                }
            )
        return vulnerabilities

    @staticmethod
    def _parse_yarn_audit(stdout: str) -> list[dict[str, object]] | None:
        raise NotImplementedError("added in Task 2")

    @staticmethod
    def _failed(
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        duration_ms: int,
    ) -> RawToolOutput:
        """Build the failure shape: an "error" key and no "vulnerabilities" list."""
        error = None
        try:
            data = json.loads(completed.stdout)
            if isinstance(data, dict):
                error = data.get("error")
        except json.JSONDecodeError:
            pass
        return RawToolOutput(
            command=" ".join(command),
            raw_output={
                "manifest_found": True,
                "error": error or "audit produced no usable advisories report",
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

Note the `_parse_yarn_audit` stub raises `NotImplementedError` - this is intentional for Task 1 (no `yarn.lock` fixture exists in Task 1's tests, so this path is never exercised yet) and gets replaced in Task 2, Step 3.

- [ ] **Step 4: Run the full test file to verify everything passes**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v`
Expected: all 8 tests pass (`test_reports_no_manifest`, `test_reports_no_vulnerabilities_on_empty_dependencies`, `test_reports_vulnerabilities_on_a_known_vulnerable_pin`, `test_reports_tool_identity`, `test_dispatches_to_npm_audit_when_package_lock_json_is_present`, `test_prefers_npm_lockfile_when_multiple_lockfiles_are_present`, `test_reports_a_failed_audit_when_no_supported_lockfile_is_present`, `test_npm_parser_skips_transitive_via_string_entries`, `test_npm_parser_reports_no_fix_available_when_fixavailable_is_false`) - 9 tests total, 0 failed.

- [ ] **Step 5: Commit**

```bash
cd radar-audit
git add src/radar_audit/runners/pnpm_audit_runner.py tests/test_pnpm_audit_runner.py
git commit -m "feat(radar-audit): dispatch dependency audit to npm when package-lock.json is present

Modified files:
- radar-audit/src/radar_audit/runners/pnpm_audit_runner.py - detect the
  target subproject's lockfile (package-lock.json/pnpm-lock.yaml/yarn.lock,
  npm-first priority) and dispatch npm audit accordingly instead of always
  running pnpm audit; extract pnpm's own parsing into _parse_pnpm_audit
- radar-audit/tests/test_pnpm_audit_runner.py - add npm dispatch, lockfile
  priority, no-lockfile-detected, and npm via-array parser edge case tests;
  replace the old no-lockfile test with the new NO_LOCKFILE_DETECTED shape"
```

---

### Task 2: yarn dispatch

**Files:**
- Modify: `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py`
- Test: `radar-audit/tests/test_pnpm_audit_runner.py`

**Interfaces:**
- Consumes: `_LOCKFILE_COMMANDS`, `_PARSER_NAMES`, `_SEVERITY_MAP`, and the `_failed()` staticmethod produced in Task 1 (all unchanged in shape/signature). The `"yarn.lock"` key already exists in both `_LOCKFILE_COMMANDS` and `_PARSER_NAMES` from Task 1's rewrite; this task only replaces the `_parse_yarn_audit` stub's body.
- Produces: a working `PnpmAuditRunner._parse_yarn_audit(stdout: str) -> list[dict] | None` static method, following the same return contract as `_parse_npm_audit`/`_parse_pnpm_audit`.

- [ ] **Step 1: Write the failing tests for yarn dispatch and the yarn-parser no-summary edge case**

Add this helper next to `_npm_install` in `radar-audit/tests/test_pnpm_audit_runner.py`:

```python
def _yarn_install(repo_path):
    subprocess.run(
        ["npx", "--package=yarn", "--", "yarn", "install"], cwd=repo_path, check=True
    )
```

Add these test functions:

```python
def test_dispatches_to_yarn_audit_when_yarn_lock_is_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps(
                {"name": "yarn-dispatch-test", "dependencies": {"lodash": "4.17.15"}}
            )
        },
    )
    _yarn_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert "yarn" in result.command
    assert result.raw_output["manifest_found"] is True
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert len(vulnerabilities) > 0
    assert all(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_yarn_parser_returns_none_when_no_summary_line_is_reached():
    stdout = '{"type":"warning","data":"something"}\n'

    result = PnpmAuditRunner._parse_yarn_audit(stdout)

    assert result is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v -k yarn`
Expected: both fail with `NotImplementedError: added in Task 2`.

- [ ] **Step 3: Replace the `_parse_yarn_audit` stub with the real NDJSON parser**

In `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py`, replace:

```python
    @staticmethod
    def _parse_yarn_audit(stdout: str) -> list[dict[str, object]] | None:
        raise NotImplementedError("added in Task 2")
```

with:

```python
    @staticmethod
    def _parse_yarn_audit(stdout: str) -> list[dict[str, object]] | None:
        # yarn classic prints one JSON object per line (not a single JSON
        # document): "auditAdvisory" records carry the same advisory shape
        # as pnpm's (id/module_name/severity/patched_versions), and a
        # trailing "auditSummary" record marks a completed run. Its absence
        # means yarn errored out before finishing the audit.
        vulnerabilities = []
        saw_summary = False
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return None
            if not isinstance(record, dict):
                return None
            record_type = record.get("type")
            if record_type == "auditAdvisory":
                advisory = record.get("data", {}).get("advisory", {})
                patched = advisory.get("patched_versions")
                vulnerabilities.append(
                    {
                        "id": str(advisory["id"]),
                        "package": advisory["module_name"],
                        "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(patched) and patched != "<0.0.0",
                    }
                )
            elif record_type == "auditSummary":
                saw_summary = True
        if not saw_summary:
            return None
        return vulnerabilities
```

- [ ] **Step 4: Run the full test file to verify everything passes**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v`
Expected: all 11 tests pass, 0 failed.

- [ ] **Step 5: Commit**

```bash
cd radar-audit
git add src/radar_audit/runners/pnpm_audit_runner.py tests/test_pnpm_audit_runner.py
git commit -m "feat(radar-audit): dispatch dependency audit to yarn when yarn.lock is present

Modified files:
- radar-audit/src/radar_audit/runners/pnpm_audit_runner.py - parse yarn
  classic's NDJSON audit output (auditAdvisory/auditSummary records),
  treating a missing trailing auditSummary as a failed audit
- radar-audit/tests/test_pnpm_audit_runner.py - add yarn dispatch and
  yarn-parser no-summary edge case tests"
```

---

### Task 3: Plan doc commit and full-suite verification

**Files:**
- Create: `docs/superpowers/plans/2026-09-24-radar-audit-dependency-audit-lockfile-dispatch.md` (this file - already created before Task 1 started; this task only commits it)

**Interfaces:**
- Consumes: nothing (mechanical wrap-up task).
- Produces: nothing further downstream; this is the branch's last task before final review.

- [ ] **Step 1: Commit the plan document**

```bash
cd /home/mlr/projets/Portfolio-Engineering-Radar
git add docs/superpowers/plans/2026-09-24-radar-audit-dependency-audit-lockfile-dispatch.md
git commit -m "docs: write radar-audit dependency-audit lockfile-dispatch implementation plan"
```

- [ ] **Step 2: Run the full radar-audit test suite**

Run: `cd radar-audit && uv run pytest`
Expected: `354 passed` (baseline of 348 after branch 4/6's merge, plus 6 net-new tests from this branch: 4 from Task 1 - `test_dispatches_to_npm_audit_when_package_lock_json_is_present`, `test_prefers_npm_lockfile_when_multiple_lockfiles_are_present`, `test_npm_parser_skips_transitive_via_string_entries`, `test_npm_parser_reports_no_fix_available_when_fixavailable_is_false` - and 2 from Task 2 - `test_dispatches_to_yarn_audit_when_yarn_lock_is_present`, `test_yarn_parser_returns_none_when_no_summary_line_is_reached`; `test_reports_a_failed_audit_when_there_is_no_lockfile` was deleted and replaced by `test_reports_a_failed_audit_when_no_supported_lockfile_is_present`, net zero on that pair), 0 failed.
