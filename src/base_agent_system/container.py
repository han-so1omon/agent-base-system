"""Container entrypoint for API and CLI execution."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or sys.argv[1:] or ["api"])
    if args[0] == "api":
        port = os.getenv("BASE_AGENT_SYSTEM_API_PORT", "8000")
        host = os.getenv("UVICORN_HOST", "0.0.0.0")
        command = [
            "uvicorn",
            "base_agent_system.api.app:create_app",
            "--factory",
            "--host",
            host,
            "--port",
            port,
        ]
        os.execvp(command[0], command)

    command = [sys.executable, "-m", "base_agent_system.cli.main", *args]
    os.execvp(command[0], command)


if __name__ == "__main__":
    raise SystemExit(main())
