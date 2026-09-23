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
