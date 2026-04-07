from __future__ import annotations

import argparse

from base_agent_system.cli.main import build_parser
from base_agent_system.extensions.registry import create_default_registry


def test_build_parser_registers_builtin_commands_through_contributors() -> None:
    parser = build_parser(extension_registry=create_default_registry())

    args = parser.parse_args(["check-connections"])

    assert args.handler(args) == "check-connections: unavailable"


def test_build_parser_includes_contributed_commands() -> None:
    class _ExtraCommandContributor:
        def register(self, parser: argparse.ArgumentParser, subparsers: argparse._SubParsersAction) -> None:
            extra = subparsers.add_parser("extra")
            extra.add_argument("value")
            extra.set_defaults(handler=lambda args: f"extra: {args.value}")

    registry = create_default_registry()
    registry.register_cli_command_contributor(_ExtraCommandContributor())

    parser = build_parser(extension_registry=registry)
    args = parser.parse_args(["extra", "hello"])

    assert args.handler(args) == "extra: hello"
