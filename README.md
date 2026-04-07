# Base Agent System

Minimal Python scaffold for a base AI agent system.

Live runtime memory uses Graphiti on top of Neo4j. Normal application runs now require valid Neo4j, Postgres, and provider configuration if you want thread memory to persist across restarts.

## Extension Model

The base system exposes explicit extension seams for workflow, ingestion, retrieval, API, and CLI behavior. Built-in behavior remains the default path, but composition now goes through an in-process registry instead of hardwired assembly.

Supported seams:
- workflow builders
- constrained workflow hooks before retrieval, after retrieval, before answer synthesis, and after answer synthesis
- ingestion connectors
- retrieval providers
- API router contributors
- CLI command contributors

Built-ins are installed through `create_default_registry()` and customizations are added with explicit registration calls such as `register_cli_command_contributor(...)`.

Example:

```python
from base_agent_system.extensions.registry import create_default_registry


class ExtraCommandContributor:
    def register(self, parser, subparsers) -> None:
        extra = subparsers.add_parser("extra")
        extra.add_argument("value")
        extra.set_defaults(handler=lambda args: f"extra: {args.value}")


registry = create_default_registry()
registry.register_cli_command_contributor(ExtraCommandContributor())
```

Current non-goals:
- no auto-discovery
- no out-of-process plugins
- no arbitrary workflow graph mutation

## Development

Run the smoke tests with:

```bash
pytest tests -q
```
