import subprocess
import sys


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "base_agent_system.cli.main", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_connections_command_runs() -> None:
    result = _run_cli("check-connections")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "check-connections: unavailable"


def test_ingest_command_accepts_path_argument() -> None:
    result = _run_cli("ingest", "docs/seed")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ingest: docs/seed"


def test_ask_command_accepts_question_argument() -> None:
    result = _run_cli("ask", "What is in the seed docs?")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ask: What is in the seed docs?"


def test_smoke_test_command_runs() -> None:
    result = _run_cli("smoke-test")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "smoke-test: unavailable"
