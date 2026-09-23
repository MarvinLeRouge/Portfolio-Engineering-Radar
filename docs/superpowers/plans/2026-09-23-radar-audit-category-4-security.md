# Category 4 (Security) Runners Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build real `ToolRunner`s and normalizers for radar-audit category 4 (Security) criteria 4.1-4.5, following the same pattern established by categories 1-3.

**Architecture:** Seven new `ToolRunner` implementations (three for 4.1, one each for 4.2-4.5) that shell out to their respective tools (via `uvx`, native binaries, or `docker run` for the three tools with no native/uvx/npx wrapper), plus five new normalizer functions that read the resulting `ToolResult` rows and write `Finding`/`Score` rows at `ScoreLevel.CRITERION`. A small shared Docker-invocation helper avoids triplicating subprocess boilerplate across the three Docker-based runners.

**Tech Stack:** Python 3.12, SQLModel, subprocess, Docker (Gitleaks/Trivy/Hadolint images), uvx (pip-audit/Semgrep), native pnpm/composer.

**Spec:** `docs/superpowers/specs/2026-09-23-radar-audit-category-4-security-design.md`

## Global Constraints

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration.
- Docker-based tools (Gitleaks, Trivy image scan, Hadolint) are always invoked via `docker run --rm ...` through the shared `run_docker_command` helper in `radar_audit/runners/docker_support.py` — not a protocol change, an internal implementation detail.
- Gitleaks always runs in git-history mode (the default `gitleaks git` subcommand) — never `--no-git`.
- `TrivyImageRunner` never builds an image as a side effect of scanning — `N/A` (`image_found: False`) if none is found locally already.
- Every `Score` row this increment writes is at `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is created here.
- The numeric severity bands (§3.1/§3.2/§3.3 of the spec) are resolved-but-provisional, pending Phase 5 portfolio-wide calibration — mark this in a code comment next to each band table, same discipline as every prior increment's thresholds.
- Tests use real subprocess/Docker invocations against `tmp_path` git fixtures — no mocking of subprocess or tool output (normalizer tests build synthetic `ToolResult.raw_output` dicts directly, matching the existing pattern in e.g. `test_normalize_dependency_circularity.py` — this is not a mock of the tool, it is testing the normalizer's own logic against a fixed input).
- Criteria 4.6a and 4.6b are explicitly **out of scope** for this increment — deferred to a later increment, same treatment as 1.4/3.5.
- Before this increment is marked done, a real `radar-audit run` must be performed against a real portfolio repo (GeoChallenge-Tracker, which already has documented Hadolint/Trivy smoke-test results in `toolchain.md`) and the resulting `Score`/`Finding` rows inspected for plausibility (Task 15).

## Review Focus

- Docker daemon unavailable when a Docker-based runner (Gitleaks/Trivy/Hadolint) executes — `subprocess.run` raises normally in that case (no daemon socket to connect to) and propagates up to the orchestrator's existing per-runner crash isolation (built and tested in increment 2.0); no new code or test is needed here, but no task in this plan may swallow that exception into a false-clean result.
- No dependency manifest present for a subproject (4.1, pip-audit/pnpm-audit/composer-audit) — must resolve to `N/A` for that stack's contribution, not a crash or a false 10.
- A repo with zero Dockerfiles anywhere (4.5) — must resolve to `N/A`, not a false-clean 10.
- No locally built Docker image matching the repo (4.4, expected to be the common case across most of the portfolio) — must resolve to `N/A`, and must never trigger a build as a side effect.
- `composer audit`'s `advisories` field switches JSON type between an object (vulnerabilities present, keyed by package name) and an empty array (clean, no packages have advisories) — confirmed empirically; must not crash when iterating either shape.

---

### Task 1: Shared Docker invocation helper

**Files:**
- Create: `radar-audit/src/radar_audit/runners/docker_support.py`
- Test: `radar-audit/tests/test_docker_support.py`

**Interfaces:**
- Produces: `run_docker_command(args: list[str], timeout_s: int, input_text: str | None = None) -> tuple[subprocess.CompletedProcess[str], int]` (the `int` is `duration_ms`). Consumed by Tasks 6, 10, 12.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_docker_support.py
from radar_audit.runners.docker_support import run_docker_command


def test_runs_a_container_and_captures_stdout():
    completed, duration_ms = run_docker_command(["alpine:latest", "echo", "hello"], timeout_s=60)

    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"
    assert duration_ms >= 0


def test_pipes_input_text_to_container_stdin():
    completed, duration_ms = run_docker_command(
        ["-i", "alpine:latest", "cat"], timeout_s=60, input_text="piped content\n"
    )

    assert completed.returncode == 0
    assert completed.stdout == "piped content\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_docker_support.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.docker_support'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/docker_support.py
from __future__ import annotations

import subprocess
import time


def run_docker_command(
    args: list[str], timeout_s: int, input_text: str | None = None
) -> tuple[subprocess.CompletedProcess[str], int]:
    """Runs `docker run --rm <args...>` and returns (completed_process, duration_ms).

    Shared by every runner that shells out to a Dockerized tool with no native
    uvx/npx wrapper (Gitleaks, Trivy image scan, Hadolint), per toolchain.md.
    `input_text`, when given, is piped to the container's stdin (Hadolint's mode).
    """
    command = ["docker", "run", "--rm", *args]
    start = time.monotonic()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        input=input_text,
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    return completed, duration_ms
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_docker_support.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/docker_support.py radar-audit/tests/test_docker_support.py
git commit -m "feat(radar-audit): add shared docker invocation helper"
```

---

### Task 2: PipAuditRunner (criterion 4.1, Python)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/pip_audit_runner.py`
- Test: `radar-audit/tests/test_pip_audit_runner.py`

**Interfaces:**
- Produces: `PipAuditRunner` (`tool_name="pip-audit"`, `scope="subproject"`, `supported_stacks=frozenset({"python"})`). `raw_output` shape: `{"manifest_found": False}` or `{"manifest_found": True, "vulnerabilities": list[{"id": str, "package": str, "severity": "MEDIUM", "fix_available": bool}]}`. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_pip_audit_runner.py
from radar_audit.runners.pip_audit_runner import PipAuditRunner

from tests.git_helpers import init_git_repo


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_a_clean_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"requirements.txt": "pyyaml==6.0.2\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"requirements.txt": "pyyaml==5.3\n"})

    runner = PipAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "pyyaml" and v["severity"] == "MEDIUM" for v in vulnerabilities)


def test_reports_tool_identity():
    runner = PipAuditRunner()

    assert runner.tool_name == "pip-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_pip_audit_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pip_audit_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/pip_audit_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

# uv-managed Python builds ship without ensurepip, which breaks pip-audit's own
# ephemeral venv creation unless forced onto the system Python -- per toolchain.md.
_PIP_AUDIT_PYTHON = "/usr/bin/python3.13"


class PipAuditRunner:
    """Runs pip-audit against a Python subproject's requirements.txt (criterion 4.1)."""

    tool_name = "pip-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "requirements.txt"
        if not manifest.exists():
            return RawToolOutput(
                command="pip-audit (skipped, no requirements.txt)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = [
            "uvx",
            "--python",
            _PIP_AUDIT_PYTHON,
            "pip-audit",
            "-r",
            "requirements.txt",
            "--format",
            "json",
        ]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={
                    "manifest_found": True,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        vulnerabilities = []
        for dependency in data.get("dependencies", []):
            for vuln in dependency.get("vulns", []):
                vulnerabilities.append(
                    {
                        "id": vuln["id"],
                        "package": dependency["name"],
                        "severity": "MEDIUM",  # pip-audit's JSON carries no severity field
                        "fix_available": bool(vuln.get("fix_versions")),
                    }
                )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_pip_audit_runner.py -v`
Expected: PASS (the vulnerable-pin test needs network access to PyPI's advisory data — same precondition class as any other pip-audit invocation)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pip_audit_runner.py radar-audit/tests/test_pip_audit_runner.py
git commit -m "feat(radar-audit): add PipAuditRunner for criterion 4.1"
```

---

### Task 3: PnpmAuditRunner (criterion 4.1, JavaScript)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/pnpm_audit_runner.py`
- Test: `radar-audit/tests/test_pnpm_audit_runner.py`

**Interfaces:**
- Produces: `PnpmAuditRunner` (`tool_name="pnpm-audit"`, `scope="subproject"`, `supported_stacks=frozenset({"javascript"})`). Same `raw_output` shape as Task 2's `PipAuditRunner`, `severity` one of `CRITICAL`/`HIGH`/`MEDIUM`/`LOW`. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_pnpm_audit_runner.py
import json
import subprocess

from radar_audit.runners.pnpm_audit_runner import PnpmAuditRunner

from tests.git_helpers import init_git_repo


def _pnpm_install(repo_path):
    subprocess.run(["pnpm", "install", "--no-frozen-lockfile"], cwd=repo_path, check=True)


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": "console.log('hi');\n"})

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_empty_dependencies(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"package.json": json.dumps({"name": "clean-test", "dependencies": {}})},
    )
    _pnpm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_pin(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "package.json": json.dumps(
                {"name": "vuln-test", "dependencies": {"lodash": "4.17.15"}}
            )
        },
    )
    _pnpm_install(repo_path)

    runner = PnpmAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "lodash" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_reports_tool_identity():
    runner = PnpmAuditRunner()

    assert runner.tool_name == "pnpm-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.pnpm_audit_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/pnpm_audit_runner.py
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


class PnpmAuditRunner:
    """Runs `pnpm audit` against a JavaScript subproject (criterion 4.1)."""

    tool_name = "pnpm-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "package.json"
        if not manifest.exists():
            return RawToolOutput(
                command="pnpm audit (skipped, no package.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = ["pnpm", "audit", "--json"]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={
                    "manifest_found": True,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        # pnpm's own JSON always uses an object keyed by advisory id here (confirmed
        # empirically, including the zero-dependency case -- `{}`, not `[]`).
        advisories = data.get("advisories", {})
        vulnerabilities = []
        if isinstance(advisories, dict):
            for advisory in advisories.values():
                patched = advisory.get("patched_versions")
                vulnerabilities.append(
                    {
                        "id": str(advisory["id"]),
                        "package": advisory["module_name"],
                        "severity": _SEVERITY_MAP.get(advisory.get("severity", ""), "MEDIUM"),
                        "fix_available": bool(patched) and patched != "<0.0.0",
                    }
                )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_pnpm_audit_runner.py -v`
Expected: PASS (needs network access to the npm registry/advisory database, and a working `pnpm install` step in the fixture)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/pnpm_audit_runner.py radar-audit/tests/test_pnpm_audit_runner.py
git commit -m "feat(radar-audit): add PnpmAuditRunner for criterion 4.1"
```

---

### Task 4: ComposerAuditRunner (criterion 4.1, PHP)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/composer_audit_runner.py`
- Test: `radar-audit/tests/test_composer_audit_runner.py`

**Interfaces:**
- Produces: `ComposerAuditRunner` (`tool_name="composer-audit"`, `scope="subproject"`, `supported_stacks=frozenset({"php"})`). Same `raw_output` shape as Task 2. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_composer_audit_runner.py
import json
import subprocess

from radar_audit.runners.composer_audit_runner import ComposerAuditRunner

from tests.git_helpers import init_git_repo


def _composer_install(repo_path):
    subprocess.run(
        ["composer", "install", "--no-interaction", "--quiet"], cwd=repo_path, check=True
    )


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.php": "<?php\n"})

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


def test_reports_no_vulnerabilities_on_a_clean_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {"name": "test/clean-test", "require": {"psr/log": "^3.0"}}
            )
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


def test_reports_vulnerabilities_on_a_known_vulnerable_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    # "audit.block-insecure: false" is required -- Composer 2.9+ refuses to *install*
    # a package with known advisories by default, confirmed empirically.
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {
                    "name": "test/vuln-test",
                    "require": {"phpmailer/phpmailer": "6.1.0"},
                    "config": {"audit": {"block-insecure": False}},
                }
            )
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "phpmailer/phpmailer" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_reports_tool_identity():
    runner = ComposerAuditRunner()

    assert runner.tool_name == "composer-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_composer_audit_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.composer_audit_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/composer_audit_runner.py
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
    "medium": "MEDIUM",
    "low": "LOW",
}


class ComposerAuditRunner:
    """Runs `composer audit` against a PHP subproject (criterion 4.1)."""

    tool_name = "composer-audit"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        manifest = target_path / "composer.json"
        if not manifest.exists():
            return RawToolOutput(
                command="composer audit (skipped, no composer.json)",
                raw_output={"manifest_found": False},
                exit_code=0,
                duration_ms=0,
            )

        command = ["composer", "audit", "--format=json"]
        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # With zero installed packages, `composer audit` prints nothing to stdout
        # ("No packages - skipping audit." goes to stderr instead) -- confirmed
        # empirically. Treat that the same as an explicit empty advisories list.
        stdout = completed.stdout.strip()
        try:
            data = json.loads(stdout) if stdout else {"advisories": []}
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={
                    "manifest_found": True,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        # Composer's own JSON uses an object keyed by package name when advisories
        # exist, but an empty *array* (not `{}`) when none do -- confirmed
        # empirically; both shapes must be handled without crashing.
        advisories = data.get("advisories", [])
        vulnerabilities = []
        if isinstance(advisories, dict):
            for package_advisories in advisories.values():
                for advisory in package_advisories:
                    vulnerabilities.append(
                        {
                            "id": advisory["advisoryId"],
                            "package": advisory["packageName"],
                            "severity": _SEVERITY_MAP.get(
                                (advisory.get("severity") or "").lower(), "MEDIUM"
                            ),
                            "fix_available": True,
                        }
                    )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"manifest_found": True, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_composer_audit_runner.py -v`
Expected: PASS (needs network access to Packagist/the FriendsOfPHP security advisories database)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/composer_audit_runner.py radar-audit/tests/test_composer_audit_runner.py
git commit -m "feat(radar-audit): add ComposerAuditRunner for criterion 4.1"
```

---

### Task 5: normalize_dependency_vulnerabilities (criterion 4.1)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/dependency_vulnerabilities.py`
- Test: `radar-audit/tests/test_normalize_dependency_vulnerabilities.py`

**Interfaces:**
- Consumes: `raw_output` shape from Tasks 2-4: `{"manifest_found": bool, "vulnerabilities": list[{"id": str, "package": str, "severity": str, "fix_available": bool}]}`.
- Produces: `normalize_dependency_vulnerabilities(session, scoring_run, criterion, tool_results) -> Score | None`, registered in Task 14 under `("Security", "Dependency vulnerabilities (CVE)")`.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_normalize_dependency_vulnerabilities.py
from radar_audit.normalizers.dependency_vulnerabilities import (
    normalize_dependency_vulnerabilities,
)
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Security", "Dependency vulnerabilities (CVE)"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, tool_name, raw_output, subproject_path="."):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=subproject_path,
        tool_name=tool_name,
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_manifest_found_anywhere_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, "pip-audit", {"manifest_found": False})

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_clean_manifest_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, "pip-audit", {"manifest_found": True, "vulnerabilities": []}
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings == []


def test_medium_severity_scores_six_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pip-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {"id": "PYSEC-2020-96", "package": "pyyaml", "severity": "MEDIUM", "fix_available": True}
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].tool_result_id == tool_result.id


def test_high_severity_scores_four(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "pnpm-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {"id": "1", "package": "lodash", "severity": "HIGH", "fix_available": True}
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0


def test_critical_severity_scores_two(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        "composer-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {
                    "id": "PKSA-x",
                    "package": "phpmailer/phpmailer",
                    "severity": "CRITICAL",
                    "fix_available": True,
                }
            ],
        },
    )

    score = normalize_dependency_vulnerabilities(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0


def test_worst_severity_wins_across_multiple_subprojects_and_tools(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    clean = _make_tool_result(
        db_session,
        audit,
        "pip-audit",
        {"manifest_found": True, "vulnerabilities": []},
        subproject_path="backend",
    )
    critical = _make_tool_result(
        db_session,
        audit,
        "pnpm-audit",
        {
            "manifest_found": True,
            "vulnerabilities": [
                {"id": "1", "package": "x", "severity": "CRITICAL", "fix_available": True}
            ],
        },
        subproject_path="frontend",
    )

    score = normalize_dependency_vulnerabilities(
        db_session, scoring_run, criterion, [clean, critical]
    )

    assert score.value == 2.0


def test_skips_tool_results_where_manifest_not_found(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    no_manifest = _make_tool_result(db_session, audit, "pip-audit", {"manifest_found": False})
    with_manifest = _make_tool_result(
        db_session, audit, "pnpm-audit", {"manifest_found": True, "vulnerabilities": []}
    )

    score = normalize_dependency_vulnerabilities(
        db_session, scoring_run, criterion, [no_manifest, with_manifest]
    )

    assert score.value == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dependency_vulnerabilities.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.dependency_vulnerabilities'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/normalizers/dependency_vulnerabilities.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RELEVANT_TOOLS = {"pip-audit", "pnpm-audit", "composer-audit"}
_SEVERITY_ENUM = {
    "CRITICAL": FindingSeverity.CRITICAL,
    "HIGH": FindingSeverity.HIGH,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
}
# Worst-severity-present bands per the category-4 spec's §3.1 -- resolved but
# provisional, pending Phase 5 portfolio-wide calibration.
_BAND_VALUE = {"NONE": 10.0, "LOW": 6.0, "MEDIUM": 6.0, "HIGH": 4.0, "CRITICAL": 2.0}
_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def normalize_dependency_vulnerabilities(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name in _RELEVANT_TOOLS and r.raw_output.get("manifest_found") is True
    ]
    if not relevant:
        return None

    worst = "NONE"
    for tool_result in relevant:
        for vuln in tool_result.raw_output.get("vulnerabilities", []):
            severity = vuln.get("severity", "MEDIUM")
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=_SEVERITY_ENUM.get(severity, FindingSeverity.MEDIUM),
                    description=f"{vuln['id']}: vulnerable dependency {vuln['package']}",
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
            if _SEVERITY_RANK.get(severity, 1) > _SEVERITY_RANK[worst]:
                worst = severity

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_BAND_VALUE[worst],
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dependency_vulnerabilities.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/dependency_vulnerabilities.py radar-audit/tests/test_normalize_dependency_vulnerabilities.py
git commit -m "feat(radar-audit): add normalizer for criterion 4.1"
```

---

### Task 6: GitleaksRunner (criterion 4.2)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/gitleaks_runner.py`
- Test: `radar-audit/tests/test_gitleaks_runner.py`

**Interfaces:**
- Consumes: `run_docker_command` from Task 1.
- Produces: `GitleaksRunner` (`tool_name="gitleaks"`, `scope="repo"`, `supported_stacks=frozenset()`). `raw_output` shape: `{"findings": list[{"rule": str, "file": str, "line": int, "match": str, "commit": str}]}`. Consumed by Task 7.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_gitleaks_runner.py
from radar_audit.runners.gitleaks_runner import GitleaksRunner

from tests.git_helpers import init_git_repo

# A high-entropy fake secret shaped like a GitHub PAT -- gitleaks' rules include an
# entropy threshold, so a low-entropy/sequential placeholder does not trigger a hit
# (confirmed empirically).
_HIGH_ENTROPY_TOKEN = "ghp_NbrnTP3fAbnFbmOHnKYaXRvj7uff0LYTH8xI"


def test_reports_no_findings_on_a_clean_repo(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = GitleaksRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"findings": []}


def test_reports_a_finding_for_a_committed_secret(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"config.py": f'API_KEY = "{_HIGH_ENTROPY_TOKEN}"\n'})

    runner = GitleaksRunner()
    result = runner.run(repo_path, exclude_paths=[])

    findings = result.raw_output["findings"]
    assert len(findings) == 1
    assert findings[0]["rule"] == "github-pat"
    assert findings[0]["file"] == "config.py"
    assert findings[0]["line"] == 1


def test_reports_tool_identity():
    runner = GitleaksRunner()

    assert runner.tool_name == "gitleaks"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_gitleaks_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.gitleaks_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/gitleaks_runner.py
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command


class GitleaksRunner:
    """Scans tracked Git history for secrets via Gitleaks (criterion 4.2).

    Always runs in git-history mode (the default `gitleaks git` subcommand), never
    `--no-git` filesystem mode -- per the config decision in toolchain.md (a raw
    filesystem scan produces false positives on legitimately gitignored local
    secret files). The report is written to a directory mounted separately from the
    repo (never inside it) -- writing into the repo risks Gitleaks re-detecting its
    own prior report as a leak on a later run, confirmed empirically.
    """

    tool_name = "gitleaks"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        with tempfile.TemporaryDirectory() as output_dir:
            args = [
                "-v",
                f"{target_path}:/repo:ro",
                "-v",
                f"{output_dir}:/output",
                "zricethezav/gitleaks",
                "git",
                "/repo",
                "--report-format",
                "json",
                "--report-path",
                "/output/report.json",
                "--exit-code",
                "0",
            ]
            completed, duration_ms = run_docker_command(args, timeout_s=self.timeout_s)

            report_path = Path(output_dir) / "report.json"
            try:
                raw_findings = json.loads(report_path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                return RawToolOutput(
                    command="docker run ... gitleaks git /repo",
                    raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )

            findings = [
                {
                    "rule": f["RuleID"],
                    "file": f["File"],
                    "line": f["StartLine"],
                    "match": f["Match"],
                    "commit": f["Commit"],
                }
                for f in raw_findings
            ]

        return RawToolOutput(
            command="docker run ... gitleaks git /repo",
            raw_output={"findings": findings},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_gitleaks_runner.py -v`
Expected: PASS (needs a local Docker daemon)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/gitleaks_runner.py radar-audit/tests/test_gitleaks_runner.py
git commit -m "feat(radar-audit): add GitleaksRunner for criterion 4.2"
```

---

### Task 7: normalize_secrets_in_history (criterion 4.2)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/secrets_in_history.py`
- Test: `radar-audit/tests/test_normalize_secrets_in_history.py`

**Interfaces:**
- Consumes: `raw_output` shape from Task 6: `{"findings": list[{"rule": str, "file": str, "line": int, "match": str, "commit": str}]}`.
- Produces: `normalize_secrets_in_history(session, scoring_run, criterion, tool_results) -> Score | None`, registered in Task 14 under `("Security", "Secrets in tracked history")`.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_normalize_secrets_in_history.py
from radar_audit.normalizers.secrets_in_history import normalize_secrets_in_history
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.enums import Confidence
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Security", "Secrets in tracked history"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="gitleaks",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_findings_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"findings": []})

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_pre_filtered_test_fixture_hit_scores_eight_with_low_confidence(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_auth.py",
                    "line": 3,
                    "match": 'fake_token = "eyJhbGciOiJIUzI1NiJ9"',
                    "commit": "abc123",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].confidence == Confidence.LOW


def test_pre_filtered_env_example_hit_scores_eight(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": ".env.prod.example",
                    "line": 5,
                    "match": "BCRYPT_ROUNDS=12",
                    "commit": "def456",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 8.0


def test_unfiltered_hit_scores_two_with_high_confidence(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "github-pat",
                    "file": "config.py",
                    "line": 1,
                    "match": 'API_KEY = "ghp_realtoken"',
                    "commit": "ghi789",
                }
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert findings[0].confidence == Confidence.HIGH


def test_one_unfiltered_hit_wins_over_several_pre_filtered_ones(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "findings": [
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_auth.py",
                    "line": 1,
                    "match": 'fake_token = "x"',
                    "commit": "a",
                },
                {
                    "rule": "generic-api-key",
                    "file": "tests/test_other.py",
                    "line": 1,
                    "match": 'mock_token = "y"',
                    "commit": "b",
                },
                {
                    "rule": "github-pat",
                    "file": "config.py",
                    "line": 1,
                    "match": 'API_KEY = "ghp_realtoken"',
                    "commit": "c",
                },
            ]
        },
    )

    score = normalize_secrets_in_history(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalize_secrets_in_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.secrets_in_history'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/normalizers/secrets_in_history.py
from __future__ import annotations

import re

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

# Pre-filter rules per quality-framework.md§3.2 (Phase 3 pilot calibration): a
# generic-api-key hit in a tests?/ path on a fake_*/mock_*/dummy_* variable, or a
# hit whose file matches .env.*.example/.template/.sample, is a probable false
# positive -- held at low confidence rather than counted as "confirmed" (the P1
# critical penalty itself is out of scope for this increment, see the spec).
_TEST_PATH_RE = re.compile(r"(^|/)tests?(/|$)")
_TEST_VAR_RE = re.compile(r"\b(fake|mock|dummy)_\w*", re.IGNORECASE)
_ENV_EXAMPLE_RE = re.compile(r"\.env\.[^/]*\.(example|template|sample)$")


def _is_pre_filtered(finding: dict) -> bool:
    if finding["rule"] == "generic-api-key":
        if _TEST_PATH_RE.search(finding["file"]) and _TEST_VAR_RE.search(finding["match"]):
            return True
    return bool(_ENV_EXAMPLE_RE.search(finding["file"]))


def normalize_secrets_in_history(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "gitleaks"]
    if not relevant:
        return None

    any_confirmed = False
    any_pre_filtered = False
    for tool_result in relevant:
        for finding in tool_result.raw_output.get("findings", []):
            pre_filtered = _is_pre_filtered(finding)
            if pre_filtered:
                any_pre_filtered = True
            else:
                any_confirmed = True
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=FindingSeverity.HIGH,
                    description=f"{finding['rule']}: potential secret in {finding['file']}",
                    file=finding["file"],
                    line=finding["line"],
                    confidence=Confidence.LOW if pre_filtered else Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )

    if any_confirmed:
        value = 2.0
    elif any_pre_filtered:
        value = 8.0
    else:
        value = 10.0

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalize_secrets_in_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/secrets_in_history.py radar-audit/tests/test_normalize_secrets_in_history.py
git commit -m "feat(radar-audit): add normalizer for criterion 4.2"
```

---

### Task 8: SemgrepRunner (criterion 4.3)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/semgrep_runner.py`
- Test: `radar-audit/tests/test_semgrep_runner.py`

**Interfaces:**
- Produces: `SemgrepRunner` (`tool_name="semgrep"`, `scope="repo"`, `supported_stacks=frozenset()`). `raw_output` shape: `{"results": list[{"check_id": str, "path": str, "start": {"line": int}, "extra": {"severity": str, "message": str}}]}`. Consumed by Task 9.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_semgrep_runner.py
from radar_audit.runners.semgrep_runner import SemgrepRunner

from tests.git_helpers import init_git_repo


def test_reports_no_findings_on_clean_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "def add(a, b):\n    return a + b\n"})

    runner = SemgrepRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["results"] == []


def test_reports_a_finding_for_shell_true_subprocess(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/vuln.py": (
                "import subprocess\n\n"
                "def run_cmd(user_input):\n"
                "    subprocess.run(user_input, shell=True)\n"
            )
        },
    )

    runner = SemgrepRunner()
    result = runner.run(repo_path, exclude_paths=[])

    results = result.raw_output["results"]
    assert len(results) >= 1
    assert any("shell" in r["check_id"] for r in results)
    assert results[0]["extra"]["severity"] in {"ERROR", "WARNING", "INFO"}


def test_reports_tool_identity():
    runner = SemgrepRunner()

    assert runner.tool_name == "semgrep"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_semgrep_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.semgrep_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/semgrep_runner.py
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class SemgrepRunner:
    """Runs Semgrep's default/auto ruleset for SAST findings (criterion 4.3).

    Uses `--config auto` (the general-purpose default ruleset), not the
    authN/authZ-focused registry packs -- those are reserved for the deferred
    criterion 4.6a.
    """

    tool_name = "semgrep"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        command = ["uvx", "semgrep", "--config", "auto", "--json"]
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
                command.extend(["--exclude", str(relative)])
            except ValueError:
                pass  # not under target_path, skip
        command.append(".")

        start = time.monotonic()
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout_s, cwd=target_path
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command=" ".join(command),
                raw_output={"stdout": completed.stdout, "stderr": completed.stderr},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command=" ".join(command),
            raw_output={"results": data.get("results", [])},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_semgrep_runner.py -v`
Expected: PASS (first run may be slower while Semgrep's registry ruleset is fetched/cached)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/semgrep_runner.py radar-audit/tests/test_semgrep_runner.py
git commit -m "feat(radar-audit): add SemgrepRunner for criterion 4.3"
```

---

### Task 9: normalize_sast_findings (criterion 4.3)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/sast_findings.py`
- Test: `radar-audit/tests/test_normalize_sast_findings.py`

**Interfaces:**
- Consumes: `raw_output` shape from Task 8: `{"results": list[{"check_id": str, "path": str, "start": {"line": int}, "extra": {"severity": str, "message": str}}]}`.
- Produces: `normalize_sast_findings(session, scoring_run, criterion, tool_results) -> Score | None`, registered in Task 14 under `("Security", "SAST findings")`.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_normalize_sast_findings.py
from radar_audit.normalizers.sast_findings import normalize_sast_findings
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Security", "SAST findings")
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="semgrep",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_results_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"results": []})

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_error_severity_scores_four_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.subprocess-shell-true",
                    "path": "src/vuln.py",
                    "start": {"line": 4},
                    "extra": {"severity": "ERROR", "message": "shell=True is dangerous"},
                }
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "src/vuln.py"
    assert findings[0].line == 4


def test_warning_severity_scores_six(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "x.warning-rule",
                    "path": "a.py",
                    "start": {"line": 1},
                    "extra": {"severity": "WARNING", "message": "m"},
                }
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 6.0


def test_worst_severity_wins_across_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "results": [
                {
                    "check_id": "x.info-rule",
                    "path": "a.py",
                    "start": {"line": 1},
                    "extra": {"severity": "INFO", "message": "m"},
                },
                {
                    "check_id": "x.error-rule",
                    "path": "b.py",
                    "start": {"line": 1},
                    "extra": {"severity": "ERROR", "message": "m"},
                },
            ]
        },
    )

    score = normalize_sast_findings(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 4.0


def test_returns_none_when_no_relevant_tool_results(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    unrelated = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="ruff-check",
        tool_version="1.0.0",
        command="stub",
        raw_output={"violations": []},
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(unrelated)
    db_session.commit()
    db_session.refresh(unrelated)

    score = normalize_sast_findings(db_session, scoring_run, criterion, [unrelated])

    assert score is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalize_sast_findings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.sast_findings'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/normalizers/sast_findings.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_RAW_SEVERITY_MAP = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
_SEVERITY_ENUM = {
    "HIGH": FindingSeverity.HIGH,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
}
# Worst-severity-present bands per the category-4 spec's §3.1 -- resolved but
# provisional, pending Phase 5 portfolio-wide calibration. Semgrep's default/auto
# config has no native CRITICAL tier, so that row is never actually reached here.
_BAND_VALUE = {"NONE": 10.0, "LOW": 6.0, "MEDIUM": 6.0, "HIGH": 4.0, "CRITICAL": 2.0}
_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def normalize_sast_findings(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "semgrep"]
    if not relevant:
        return None

    worst = "NONE"
    for tool_result in relevant:
        for result in tool_result.raw_output.get("results", []):
            raw_severity = result["extra"]["severity"]
            severity = _RAW_SEVERITY_MAP.get(raw_severity, "MEDIUM")
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=_SEVERITY_ENUM.get(severity, FindingSeverity.MEDIUM),
                    description=f"{result['check_id']}: {result['extra']['message']}",
                    file=result["path"],
                    line=result["start"]["line"],
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
            if _SEVERITY_RANK.get(severity, 1) > _SEVERITY_RANK[worst]:
                worst = severity

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_BAND_VALUE[worst],
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalize_sast_findings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/sast_findings.py radar-audit/tests/test_normalize_sast_findings.py
git commit -m "feat(radar-audit): add normalizer for criterion 4.3"
```

---

### Task 10: TrivyImageRunner (criterion 4.4)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/trivy_image_runner.py`
- Test: `radar-audit/tests/test_trivy_image_runner.py`

**Interfaces:**
- Consumes: `run_docker_command` from Task 1.
- Produces: `TrivyImageRunner` (`tool_name="trivy-image"`, `scope="repo"`, `supported_stacks=frozenset()`). `raw_output` shape: `{"image_found": False}` or `{"image_found": True, "image": str, "vulnerabilities": list[{"id": str, "severity": str, "pkg": str, "fix_version": str | None}]}`. Consumed by Task 11.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_trivy_image_runner.py
import subprocess

from radar_audit.runners.trivy_image_runner import TrivyImageRunner

from tests.git_helpers import init_git_repo


def test_reports_image_not_found_when_no_local_image_matches(tmp_path):
    repo_path = tmp_path / "repo-with-no-image"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = TrivyImageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"image_found": False}


def test_reports_vulnerabilities_when_a_matching_local_image_exists(tmp_path):
    repo_path = tmp_path / "trivyimgtest"
    init_git_repo(repo_path, files={"Dockerfile": "FROM alpine:latest\n"})
    image_tag = f"{repo_path.name.lower()}:latest"
    subprocess.run(
        ["docker", "build", "-t", image_tag, str(repo_path)], check=True, capture_output=True
    )
    try:
        runner = TrivyImageRunner()
        result = runner.run(repo_path, exclude_paths=[])

        assert result.raw_output["image_found"] is True
        assert result.raw_output["image"] == image_tag
        assert isinstance(result.raw_output["vulnerabilities"], list)
        for vuln in result.raw_output["vulnerabilities"]:
            assert vuln["severity"] in {"HIGH", "CRITICAL"}
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_reports_tool_identity():
    runner = TrivyImageRunner()

    assert runner.tool_name == "trivy-image"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_trivy_image_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.trivy_image_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/trivy_image_runner.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command


class TrivyImageRunner:
    """Scans an already-built local Docker image for HIGH/CRITICAL CVEs (criterion 4.4).

    Never builds an image itself -- if no locally built image matching the repo is
    found, reports `image_found: False` rather than triggering a build (per the
    precondition documented in toolchain.md).
    """

    tool_name = "trivy-image"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 180

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        image = self._find_local_image(target_path)
        if image is None:
            return RawToolOutput(
                command="trivy image (skipped, no local image found)",
                raw_output={"image_found": False},
                exit_code=0,
                duration_ms=0,
            )

        args = [
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "aquasec/trivy",
            "image",
            "--format",
            "json",
            "--severity",
            "HIGH,CRITICAL",
            "--scanners",
            "vuln",
            image,
        ]
        completed, duration_ms = run_docker_command(args, timeout_s=self.timeout_s)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command="docker run ... trivy image",
                raw_output={"image_found": True, "image": image, "stdout": completed.stdout},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        vulnerabilities = []
        for result in data.get("Results", []) or []:
            for vuln in result.get("Vulnerabilities", []) or []:
                vulnerabilities.append(
                    {
                        "id": vuln["VulnerabilityID"],
                        "severity": vuln["Severity"],
                        "pkg": vuln["PkgName"],
                        "fix_version": vuln.get("FixedVersion") or None,
                    }
                )

        return RawToolOutput(
            command="docker run ... trivy image",
            raw_output={"image_found": True, "image": image, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _find_local_image(self, target_path: Path) -> str | None:
        repo_name = target_path.name.lower()
        if not repo_name:
            return None
        completed = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in completed.stdout.splitlines():
            repository = line.split(":", 1)[0]
            if repo_name in repository.lower():
                return line.strip()
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_trivy_image_runner.py -v`
Expected: PASS (needs a local Docker daemon; the second test builds and removes a throwaway image, and its vulnerability-count assertion is intentionally loose since a base image's CVE profile changes over time)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/trivy_image_runner.py radar-audit/tests/test_trivy_image_runner.py
git commit -m "feat(radar-audit): add TrivyImageRunner for criterion 4.4"
```

---

### Task 11: normalize_container_image_vulnerabilities (criterion 4.4)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/container_image_vulnerabilities.py`
- Test: `radar-audit/tests/test_normalize_container_image_vulnerabilities.py`

**Interfaces:**
- Consumes: `raw_output` shape from Task 10.
- Produces: `normalize_container_image_vulnerabilities(session, scoring_run, criterion, tool_results) -> Score | None`, registered in Task 14 under `("Security", "Container image vulnerabilities")`.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_normalize_container_image_vulnerabilities.py
from radar_audit.normalizers.container_image_vulnerabilities import (
    normalize_container_image_vulnerabilities,
)
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(
        db_session, methodology_version.id, "Security", "Container image vulnerabilities"
    )
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="trivy-image",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_image_found_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"image_found": False})

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score is None


def test_image_found_with_no_vulnerabilities_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"image_found": True, "image": "app:latest", "vulnerabilities": []}
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 10.0


def test_high_severity_vulnerability_scores_four_and_creates_a_finding(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "image_found": True,
            "image": "app:latest",
            "vulnerabilities": [
                {"id": "CVE-2024-1", "severity": "HIGH", "pkg": "openssl", "fix_version": "3.1"}
            ],
        },
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 4.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1


def test_critical_severity_vulnerability_scores_two(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "image_found": True,
            "image": "app:latest",
            "vulnerabilities": [
                {"id": "CVE-2024-2", "severity": "CRITICAL", "pkg": "libx", "fix_version": None}
            ],
        },
    )

    score = normalize_container_image_vulnerabilities(
        db_session, scoring_run, criterion, [tool_result]
    )

    assert score.value == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalize_container_image_vulnerabilities.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.container_image_vulnerabilities'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/normalizers/container_image_vulnerabilities.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

_SEVERITY_ENUM = {"HIGH": FindingSeverity.HIGH, "CRITICAL": FindingSeverity.CRITICAL}
# Trivy is invoked with --severity HIGH,CRITICAL (per toolchain.md), so only these
# two rows of the band table are ever reachable -- provisional pending Phase 5
# portfolio-wide calibration, per the category-4 spec's §3.1.
_BAND_VALUE = {"NONE": 10.0, "HIGH": 4.0, "CRITICAL": 2.0}
_SEVERITY_RANK = {"NONE": 0, "HIGH": 1, "CRITICAL": 2}


def normalize_container_image_vulnerabilities(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [
        r
        for r in tool_results
        if r.tool_name == "trivy-image" and r.raw_output.get("image_found") is True
    ]
    if not relevant:
        return None

    worst = "NONE"
    for tool_result in relevant:
        for vuln in tool_result.raw_output.get("vulnerabilities", []):
            severity = vuln.get("severity", "HIGH")
            session.add(
                Finding(
                    scoring_run_id=scoring_run.id,
                    criterion_id=criterion.id,
                    tool_result_id=tool_result.id,
                    severity=_SEVERITY_ENUM.get(severity, FindingSeverity.HIGH),
                    description=f"{vuln['id']}: {vuln['pkg']}",
                    confidence=Confidence.HIGH,
                    status=FindingStatus.OPEN,
                    human_verdict=HumanVerdict.UNREVIEWED,
                )
            )
            if _SEVERITY_RANK.get(severity, 1) > _SEVERITY_RANK[worst]:
                worst = severity

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=_BAND_VALUE[worst],
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalize_container_image_vulnerabilities.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/container_image_vulnerabilities.py radar-audit/tests/test_normalize_container_image_vulnerabilities.py
git commit -m "feat(radar-audit): add normalizer for criterion 4.4"
```

---

### Task 12: HadolintRunner (criterion 4.5)

**Files:**
- Create: `radar-audit/src/radar_audit/runners/hadolint_runner.py`
- Test: `radar-audit/tests/test_hadolint_runner.py`

**Interfaces:**
- Consumes: `run_docker_command` from Task 1.
- Produces: `HadolintRunner` (`tool_name="hadolint"`, `scope="repo"`, `supported_stacks=frozenset()`). `raw_output` shape: `{"dockerfiles": list[{"path": str, "findings": list[{"code": str, "column": int, "file": str, "level": str, "line": int, "message": str}]}]}`. Consumed by Task 13.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_hadolint_runner.py
from radar_audit.runners.hadolint_runner import HadolintRunner

from tests.git_helpers import init_git_repo


def test_reports_no_dockerfiles(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"dockerfiles": []}


def test_reports_a_clean_dockerfile(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"Dockerfile": "FROM alpine:3.19\nCMD [\"echo\", \"hi\"]\n"},
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert dockerfiles[0]["path"] == "Dockerfile"
    assert dockerfiles[0]["findings"] == []


def test_reports_findings_for_an_unpinned_apt_install(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"Dockerfile": "FROM ubuntu:20.04\nRUN apt-get update && apt-get install -y curl\n"},
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert len(dockerfiles[0]["findings"]) > 0
    assert any(f["code"] == "DL3008" for f in dockerfiles[0]["findings"])


def test_excludes_vendored_dockerfiles(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "Dockerfile": "FROM alpine:3.19\n",
            "vendor/laravel/sail/runtimes/8.2/Dockerfile": "FROM ubuntu:20.04\n",
        },
    )

    runner = HadolintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    dockerfiles = result.raw_output["dockerfiles"]
    assert len(dockerfiles) == 1
    assert dockerfiles[0]["path"] == "Dockerfile"


def test_reports_tool_identity():
    runner = HadolintRunner()

    assert runner.tool_name == "hadolint"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_hadolint_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.runners.hadolint_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/runners/hadolint_runner.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command

# Matches the discovery pitfall documented in toolchain.md: naive Dockerfile
# discovery on Summit-Stats surfaced vendored/third-party Dockerfiles (e.g.
# vendor/laravel/sail/runtimes/*/Dockerfile) as noise.
_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__", ".git"}


class HadolintRunner:
    """Lints every discovered Dockerfile with Hadolint (criterion 4.5)."""

    tool_name = "hadolint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        dockerfiles = self._discover_dockerfiles(target_path, exclude_paths)

        results = []
        total_duration_ms = 0
        for dockerfile in dockerfiles:
            completed, duration_ms = run_docker_command(
                ["-i", "hadolint/hadolint", "hadolint", "--format", "json", "-"],
                timeout_s=self.timeout_s,
                input_text=dockerfile.read_text(),
            )
            total_duration_ms += duration_ms
            try:
                findings = json.loads(completed.stdout)
            except json.JSONDecodeError:
                findings = []
            results.append(
                {"path": str(dockerfile.relative_to(target_path)), "findings": findings}
            )

        return RawToolOutput(
            command="docker run ... hadolint --format json -",
            raw_output={"dockerfiles": results},
            exit_code=0,
            duration_ms=total_duration_ms,
        )

    def _discover_dockerfiles(self, target_path: Path, exclude_paths: list[Path]) -> list[Path]:
        found = []
        for candidate in target_path.rglob("Dockerfile*"):
            if not candidate.is_file():
                continue
            relative_parts = candidate.relative_to(target_path).parts
            if any(part in _SKIP_DIRNAMES for part in relative_parts):
                continue
            if any(
                excluded == candidate or excluded in candidate.parents
                for excluded in exclude_paths
            ):
                continue
            found.append(candidate)
        return sorted(found)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_hadolint_runner.py -v`
Expected: PASS (needs a local Docker daemon)

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/runners/hadolint_runner.py radar-audit/tests/test_hadolint_runner.py
git commit -m "feat(radar-audit): add HadolintRunner for criterion 4.5"
```

---

### Task 13: normalize_dockerfile_hardening (criterion 4.5)

**Files:**
- Create: `radar-audit/src/radar_audit/normalizers/dockerfile_hardening.py`
- Test: `radar-audit/tests/test_normalize_dockerfile_hardening.py`

**Interfaces:**
- Consumes: `raw_output` shape from Task 12.
- Produces: `normalize_dockerfile_hardening(session, scoring_run, criterion, tool_results) -> Score | None`, registered in Task 14 under `("Security", "Dockerfile hardening")`.

- [ ] **Step 1: Write the failing test**

```python
# radar-audit/tests/test_normalize_dockerfile_hardening.py
from radar_audit.normalizers.dockerfile_hardening import normalize_dockerfile_hardening
from radar_audit.normalizers.shared import get_criterion, get_or_create_scoring_run
from radar_audit.taxonomy.seed import seed_taxonomy
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding
from radar_core.models.repository import Repository
from sqlmodel import select


def _make_scoring_run_and_criterion(db_session):
    repo = Repository(name="repo", path="/tmp/repo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    audit = Audit(repository_id=repo.id, commit_sha="a" * 40, is_dirty=False)
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    methodology_version = seed_taxonomy(db_session)
    scoring_run = get_or_create_scoring_run(db_session, audit, methodology_version)
    criterion = get_criterion(db_session, methodology_version.id, "Security", "Dockerfile hardening")
    return audit, scoring_run, criterion


def _make_tool_result(db_session, audit, raw_output):
    tool_result = ToolResult(
        audit_id=audit.id,
        subproject_path=".",
        tool_name="hadolint",
        tool_version="1.0.0",
        command="stub",
        raw_output=raw_output,
        exit_code=0,
        duration_ms=1,
    )
    db_session.add(tool_result)
    db_session.commit()
    db_session.refresh(tool_result)
    return tool_result


def test_no_dockerfiles_returns_none(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(db_session, audit, {"dockerfiles": []})

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score is None


def test_one_clean_dockerfile_scores_ten(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session, audit, {"dockerfiles": [{"path": "Dockerfile", "findings": []}]}
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 10.0


def test_one_dirty_dockerfile_of_two_scores_five_and_creates_findings(db_session):
    audit, scoring_run, criterion = _make_scoring_run_and_criterion(db_session)
    tool_result = _make_tool_result(
        db_session,
        audit,
        {
            "dockerfiles": [
                {"path": "Dockerfile", "findings": []},
                {
                    "path": "backend/Dockerfile",
                    "findings": [
                        {
                            "code": "DL3008",
                            "column": 1,
                            "file": "-",
                            "level": "warning",
                            "line": 2,
                            "message": "Pin versions in apt get install",
                        }
                    ],
                },
            ]
        },
    )

    score = normalize_dockerfile_hardening(db_session, scoring_run, criterion, [tool_result])

    assert score.value == 5.0
    findings = db_session.exec(select(Finding).where(Finding.criterion_id == criterion.id)).all()
    assert len(findings) == 1
    assert findings[0].file == "backend/Dockerfile"
    assert findings[0].line == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dockerfile_hardening.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'radar_audit.normalizers.dockerfile_hardening'`

- [ ] **Step 3: Write minimal implementation**

```python
# radar-audit/src/radar_audit/normalizers/dockerfile_hardening.py
from __future__ import annotations

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import ToolResult
from radar_core.models.finding import Finding
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session


def normalize_dockerfile_hardening(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
) -> Score | None:
    relevant = [r for r in tool_results if r.tool_name == "hadolint"]
    if not relevant:
        return None

    clean = 0
    total = 0
    for tool_result in relevant:
        for entry in tool_result.raw_output.get("dockerfiles", []):
            total += 1
            findings = entry.get("findings", [])
            if not findings:
                clean += 1
                continue
            for finding in findings:
                session.add(
                    Finding(
                        scoring_run_id=scoring_run.id,
                        criterion_id=criterion.id,
                        tool_result_id=tool_result.id,
                        severity=FindingSeverity.LOW,
                        description=f"{finding['code']}: {finding['message']}",
                        file=entry["path"],
                        line=finding.get("line"),
                        confidence=Confidence.HIGH,
                        status=FindingStatus.OPEN,
                        human_verdict=HumanVerdict.UNREVIEWED,
                    )
                )

    if total == 0:
        return None

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=(clean / total) * 10,
        confidence=Confidence.HIGH,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalize_dockerfile_hardening.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/normalizers/dockerfile_hardening.py radar-audit/tests/test_normalize_dockerfile_hardening.py
git commit -m "feat(radar-audit): add normalizer for criterion 4.5"
```

---

### Task 14: Register all category-4 runners and normalizers

**Files:**
- Modify: `radar-audit/src/radar_audit/cli.py:1-65` (imports + `DEFAULT_RUNNERS`)
- Modify: `radar-audit/src/radar_audit/normalizers/__init__.py` (imports + `CRITERION_NORMALIZERS`)
- Modify: `radar-audit/tests/test_normalizer_registry.py:6-7`

**Interfaces:**
- Consumes: all seven runner classes (Tasks 2, 3, 4, 6, 8, 10, 12) and all five normalizer functions (Tasks 5, 7, 9, 11, 13).

- [ ] **Step 1: Write the failing test**

Update the registry count assertion in `radar-audit/tests/test_normalizer_registry.py`:

```python
def test_registry_has_exactly_the_seventeen_tooled_criteria():
    assert len(CRITERION_NORMALIZERS) == 17
```

(Replaces the existing `test_registry_has_exactly_the_twelve_tooled_criteria`, same function body otherwise unchanged -- rename it to keep the count accurate in its own name, per this codebase's existing convention.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd radar-audit && uv run pytest tests/test_normalizer_registry.py -v`
Expected: FAIL — `assert 12 == 17`

- [ ] **Step 3: Write minimal implementation**

In `radar-audit/src/radar_audit/normalizers/__init__.py`, add the five new imports and registry entries:

```python
from radar_audit.normalizers.container_image_vulnerabilities import (
    normalize_container_image_vulnerabilities,
)
from radar_audit.normalizers.dependency_vulnerabilities import (
    normalize_dependency_vulnerabilities,
)
from radar_audit.normalizers.dockerfile_hardening import normalize_dockerfile_hardening
from radar_audit.normalizers.sast_findings import normalize_sast_findings
from radar_audit.normalizers.secrets_in_history import normalize_secrets_in_history
```

Add to `CRITERION_NORMALIZERS`:

```python
    ("Security", "Dependency vulnerabilities (CVE)"): normalize_dependency_vulnerabilities,
    ("Security", "Secrets in tracked history"): normalize_secrets_in_history,
    ("Security", "SAST findings"): normalize_sast_findings,
    ("Security", "Container image vulnerabilities"): normalize_container_image_vulnerabilities,
    ("Security", "Dockerfile hardening"): normalize_dockerfile_hardening,
```

In `radar-audit/src/radar_audit/cli.py`, add the seven new runner imports:

```python
from radar_audit.runners.composer_audit_runner import ComposerAuditRunner
from radar_audit.runners.gitleaks_runner import GitleaksRunner
from radar_audit.runners.hadolint_runner import HadolintRunner
from radar_audit.runners.pip_audit_runner import PipAuditRunner
from radar_audit.runners.pnpm_audit_runner import PnpmAuditRunner
from radar_audit.runners.semgrep_runner import SemgrepRunner
from radar_audit.runners.trivy_image_runner import TrivyImageRunner
```

Append to `DEFAULT_RUNNERS`:

```python
    PipAuditRunner(),
    PnpmAuditRunner(),
    ComposerAuditRunner(),
    GitleaksRunner(),
    SemgrepRunner(),
    TrivyImageRunner(),
    HadolintRunner(),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd radar-audit && uv run pytest tests/test_normalizer_registry.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add radar-audit/src/radar_audit/cli.py radar-audit/src/radar_audit/normalizers/__init__.py radar-audit/tests/test_normalizer_registry.py
git commit -m "feat(radar-audit): register category 4 runners and normalizers"
```

---

### Task 15: Real-repo validation

**Files:** None created or modified — this task is a manual validation pass, per this project's standing convention of always validating a new increment against a real portfolio repo before considering it done.

**Interfaces:** None.

- [ ] **Step 1: Run the full test suite**

Run: `cd radar-audit && uv run pytest`
Expected: PASS, all tests including the fourteen prior tasks' new tests

- [ ] **Step 2: Run a real audit against GeoChallenge-Tracker**

```bash
export RADAR_DATABASE_URL="sqlite:////tmp/radar-audit-category-4-validation.db"
cd radar-audit
uv run alembic -c ../radar-core/alembic.ini upgrade head
uv run radar-audit run <path-to-GeoChallenge-Tracker-checkout>
uv run radar-audit score <path-to-GeoChallenge-Tracker-checkout>
uv run radar-audit report <path-to-GeoChallenge-Tracker-checkout>
```

- [ ] **Step 3: Inspect the generated report for plausibility**

Open the generated report (path printed by the `report` command) and confirm:
- The Security category now shows real scores for criteria 4.1-4.5 instead of "Not yet audited".
- 4.4 (Container image vulnerabilities) is `N/A` unless GeoChallenge-Tracker's backend image has already been built locally (per `toolchain.md`'s documented precondition), matching what actually happened in this run.
- 4.5 (Dockerfile hardening) reflects the previously smoke-tested `backend/Dockerfile` findings (3 plausible low-noise findings per `toolchain.md`), not zero and not wildly more.
- No criterion silently crashed the whole audit — check the `run` command's own output for any per-runner failure and confirm it did not abort other runners (existing per-runner crash isolation).

- [ ] **Step 4: Fix any plausibility issues found**

If a finding is clearly wrong (e.g. a criterion is always `N/A` when it shouldn't be, or a severity band is obviously miscalibrated against real output), fix it directly in the relevant runner/normalizer file, add a regression test capturing the real-world case that was missed, and commit the fix separately from the exploratory validation run.

```bash
git add <fixed files> <new regression test>
git commit -m "fix(radar-audit): <describe the real-world case fixed>"
```

- [ ] **Step 5: Clean up the validation database**

```bash
rm -f /tmp/radar-audit-category-4-validation.db
```

No commit for this step — it only removes a local scratch file, not a tracked one.
