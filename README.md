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

Opik is optional and disabled by default. When enabled, the system treats one interaction branch execution as the canonical trace unit, with `thread_id` used for grouping and parent-child interaction ids used for tree correlation.

Environment variables:

```bash
export BASE_AGENT_SYSTEM_OPIK_ENABLED=true
export BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME=base-agent-system
export BASE_AGENT_SYSTEM_OPIK_WORKSPACE=...
export BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME=OPIK_API_KEY
export BASE_AGENT_SYSTEM_OPIK_URL=https://opik.example.com
export BASE_AGENT_SYSTEM_OPIK_USE_LOCAL=false
export OPIK_API_KEY=...
```

Evaluation metrics are intentionally extensible. Runtime tracing records primitive signals such as tool count, retrieval hits, citation count, artifact count, and branch status. Derived scores are computed separately through a pluggable metric registry so metrics can be versioned and expanded without changing the runtime trace contract.

Skill content is tool-managed in this repository. The tracked source of truth is `skills-lock.json`, and the local `skills/` directory should be refreshed with:

```bash
npx skills update
```

Do not hand-edit files under `skills/` in this repository; regenerate them from the lock file instead.

Run the smoke tests with:

```bash
pytest tests -q
```

## Web Chat UI

A small `Next.js` app lives in `web/` and uses `Vercel AI SDK` for chat ergonomics while delegating real query execution to the FastAPI backend.

The frontend architecture is intentionally thin:
- `web/app/page.tsx` provides the operator chat UI
- FastAPI remains the system of record for retrieval, memory, persistence, and LLM invocation
- the backend LangGraph ReAct agent uses OpenAI directly with `gpt-4o-mini` by default
- `/interact` remains the canonical execution API
- `/api/chat` stays the write and stream adapter for the packaged UI
- `/threads` and `/threads/{thread_id}/interactions` provide read-only thread browsing for the sidebar and history view

For the local `kind` deployment, the packaged chat UI is also served through the cluster ingress at `http://127.0.0.1:8000/chat`.

The packaged UI now creates a new thread on the first operator message, lists recent threads in a sidebar, and reopens existing threads by calling the thread browsing APIs before continuing the same `thread_id` through `/api/chat`.

Public thread browsing intentionally excludes internal reasoning. Debug interaction details live behind `/debug/threads/{thread_id}/interactions/{interaction_id}` and are disabled in production by default unless `BASE_AGENT_SYSTEM_DEBUG_INTERACTIONS_ENABLED=true` is set.

To run it locally:

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Set `BASE_AGENT_SYSTEM_API_URL` in `web/.env.local` to your FastAPI base URL, for example `http://127.0.0.1:8000`.
