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
