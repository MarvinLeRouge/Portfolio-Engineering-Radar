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
