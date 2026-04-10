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
export BASE_AGENT_SYSTEM_LLM_MODEL=gpt-4o-mini
export OPENAI_API_KEY=...
```

Optional Opik setup:

```bash
export BASE_AGENT_SYSTEM_OPIK_ENABLED=true
export BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME=base-agent-system
export BASE_AGENT_SYSTEM_OPIK_WORKSPACE=...
export BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME=OPIK_API_KEY
export BASE_AGENT_SYSTEM_OPIK_URL=https://opik.example.com
export BASE_AGENT_SYSTEM_OPIK_USE_LOCAL=false
export OPIK_API_KEY=...
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
curl -X POST http://127.0.0.1:8000/interact \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","messages":[{"role":"user","content":"What does the markdown ingestion service do?"}]}'
```

Expected: non-empty `citations` and `debug.document_hits >= 1`.

The backend owns LLM invocation. The canonical backend interaction API is `/interact`, and the web chat UI routes through `/api/chat`, which adapts into the same LangGraph ReAct agent using OpenAI directly with `gpt-4o-mini` by default.

The UI now uses separate read-only browsing endpoints for transcript history:

- `GET /threads` lists recent thread summaries for the sidebar
- `GET /threads/{thread_id}/interactions?limit=20` loads the newest visible interactions first
- `before_ts` plus `before_id` acts as the upward-pagination cursor for older interactions

The packaged chat page starts a new thread automatically on the first operator message, then reuses that `thread_id` on later sends so LangGraph continuation and semantic memory stay aligned.

Debug-only step and reasoning details are available at `/debug/threads/{thread_id}/interactions/{interaction_id}`, but that endpoint is disabled in production by default. Enable it only with explicit `BASE_AGENT_SYSTEM_DEBUG_INTERACTIONS_ENABLED=true` in a trusted environment.

8. Verify persistent memory with:

```bash
curl -X POST http://127.0.0.1:8000/interact \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","messages":[{"role":"user","content":"Remember that my preferred deployment target is Kubernetes."}]}'

curl -X POST http://127.0.0.1:8000/interact \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"smoke-thread","messages":[{"role":"user","content":"What is my preferred deployment target?"}]}'
```

Expected: the second response mentions `Kubernetes` and `debug.memory_hits >= 1`.

Opik operating model:
- canonical trace unit: one interaction branch execution
- thread-level analysis: group traces by `thread_id`
- delegated work: group child traces by `parent_interaction_id`
- evaluation metrics: compute derived scores from primitive runtime signals through a pluggable, versioned metric registry

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
