"""Minimal CLI entrypoint backed by shared services."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from base_agent_system.app_state import AppState
from base_agent_system.dependencies import create_app_state, dependency_status


def shared_services(app_state: AppState | None = None) -> dict[str, object]:
    try:
        state = app_state or create_app_state()
        status = dependency_status(state)
    except ValueError:
        state = None
        status = {"neo4j": False, "postgres": False}
    availability = "available" if all(status.values()) else "unavailable"
    return {"state": state, "availability": availability}


def run_check_connections(app_state: AppState | None = None) -> str:
    services = shared_services(app_state)
    return f"check-connections: {services['availability']}"


def run_ingest(path: str, app_state: AppState | None = None) -> str:
    shared_services(app_state)
    return f"ingest: {path}"


def run_ask(question: str, app_state: AppState | None = None) -> str:
    shared_services(app_state)
    return f"ask: {question}"


def run_smoke_test(app_state: AppState | None = None) -> str:
    services = shared_services(app_state)
    return f"smoke-test: {services['availability']}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="base-agent-system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-connections")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("path")

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question")

    subparsers.add_parser("smoke-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check-connections":
        print(run_check_connections())
    elif args.command == "ingest":
        print(run_ingest(args.path))
    elif args.command == "ask":
        print(run_ask(args.question))
    else:
        print(run_smoke_test())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
