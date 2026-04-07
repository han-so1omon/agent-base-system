# Local Development

## Extending The Base System

The runtime uses explicit registration through `create_default_registry()` for ingestion, retrieval, workflow, API, and CLI seams. That keeps the shipped behavior stable while letting local code add targeted extensions without replacing the whole app.

Supported extension seams:
- ingestion connectors
- retrieval providers
- workflow builders
- constrained workflow hooks
- API router contributors
- CLI command contributors

Example CLI extension:

```python
from base_agent_system.cli.main import build_parser
from base_agent_system.extensions.registry import create_default_registry


class ExtraCommandContributor:
    def register(self, parser, subparsers) -> None:
        extra = subparsers.add_parser("extra")
        extra.add_argument("value")
        extra.set_defaults(handler=lambda args: f"extra: {args.value}")


registry = create_default_registry()
registry.register_cli_command_contributor(ExtraCommandContributor())
parser = build_parser(extension_registry=registry)
```

Current non-goals:
- no auto-discovery
- no out-of-process plugins
- no arbitrary workflow graph mutation

1. Install the package in a Python 3.11 environment with `pip install -e .[dev]`.
2. Export the runtime environment variables:

```bash
export BASE_AGENT_SYSTEM_NEO4J_URI=bolt://localhost:7687
export BASE_AGENT_SYSTEM_NEO4J_USER=neo4j
export BASE_AGENT_SYSTEM_NEO4J_PASSWORD=password
export BASE_AGENT_SYSTEM_NEO4J_DATABASE=neo4j
export BASE_AGENT_SYSTEM_POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/app
export OPENAI_API_KEY=...
```

3. Run `python3 -m base_agent_system.cli.main check-connections` to confirm config loads.
4. Start the API with `python3 -m uvicorn base_agent_system.api.app:create_app --factory --host 127.0.0.1 --port 8000`.
5. Check `GET /live` and `GET /ready`.
6. Ingest docs with:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"path":"docs/seed"}'
```

7. Verify retrieval with:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","query":"What does the markdown ingestion service do?"}'
```

Expected: non-empty `citations` and `debug.document_hits >= 1`.

8. Verify persistent memory with:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","query":"Remember that my preferred deployment target is Kubernetes."}'

curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","query":"What is my preferred deployment target?"}'
```

Expected: the second response mentions `Kubernetes` and `debug.memory_hits >= 1`.

9. Restart the API process and ask the memory question again.

Expected: the remembered answer still appears after restart.

10. Inspect Neo4j Browser with:

```cypher
MATCH (n)
WHERE n.group_id = "smoke-thread"
RETURN n
LIMIT 25;
```

Expected: thread-linked graph memory is visible in Neo4j.
