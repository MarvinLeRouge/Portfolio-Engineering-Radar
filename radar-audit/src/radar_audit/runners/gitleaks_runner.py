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
    `--no-git` filesystem mode - per the config decision in toolchain.md (a raw
    filesystem scan produces false positives on legitimately gitignored local
    secret files). The report is written to a directory mounted separately from the
    repo (never inside it) - writing into the repo risks Gitleaks re-detecting its
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
                # Replaces the secret value with REDACTED in Match/Secret so no raw
                # credential is persisted in ToolResult.raw_output.
                "--redact",
            ]
            completed, duration_ms = run_docker_command(args, timeout_s=self.timeout_s)

            # Gitleaks exits 0 and writes a valid empty report ("[]") when the
            # target has no readable git history (e.g. a worktree pointer file,
            # or a directory with no .git at all) - it logs this fatal error to
            # stderr instead of failing the process, so an empty findings list
            # alone cannot distinguish "clean scan" from "never scanned".
            if "fatal: not a git repository" in completed.stderr:
                return RawToolOutput(
                    command="docker run ... gitleaks git /repo",
                    raw_output={
                        "error": "gitleaks could not read the target's git history",
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                    exit_code=1,
                    duration_ms=duration_ms,
                )

            report_path = Path(output_dir) / "report.json"
            try:
                raw_findings = json.loads(report_path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                return RawToolOutput(
                    command="docker run ... gitleaks git /repo",
                    # Failure shape: an "error" key and no "findings" list.
                    raw_output={
                        "error": "gitleaks produced no readable report",
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
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
