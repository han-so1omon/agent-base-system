# Extensibility First Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the repo into a reusable base system by adding explicit extension seams for workflows, ingestion, retrieval, API routes, and CLI commands.

**Architecture:** Keep the current built-in behavior as the default path, but move composition behind a small in-process registry plus typed extension contracts. Avoid package discovery, plugin loading frameworks, and arbitrary graph mutation; start with explicit registration and constrained hook points.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Graphiti/Neo4j, Postgres, Helmfile, pytest

---

### Task 1: Add Extension Contracts And Registry

**Files:**
- Create: `src/base_agent_system/extensions/contracts.py`
- Create: `src/base_agent_system/extensions/registry.py`
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/dependencies.py`
- Test: `tests/integration/test_config.py`
- Test: `tests/integration/test_extensions_registry.py`

**Step 1: Write the failing tests**

Add tests for:
- default built-in registrations exist
- duplicate registration raises
- unknown plugin key raises

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_extensions_registry.py -q
```

Expected: FAIL because the registry and contracts do not exist yet.

**Step 3: Write minimal implementation**

Add Protocols or simple typed contracts for:
- workflow builder
- ingestion connector
- retrieval provider
- API router contributor
- CLI command contributor

Add a registry that supports explicit registration and lookup.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_extensions_registry.py tests/integration/test_config.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/extensions src/base_agent_system/runtime_services.py src/base_agent_system/dependencies.py tests/integration/test_extensions_registry.py tests/integration/test_config.py
git commit -m "feat: add extension registry contracts"
```

### Task 2: Split Runtime Composition Into Small Factories

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/app_state.py`
- Modify: `src/base_agent_system/dependencies.py`
- Test: `tests/integration/test_workflow.py`

**Step 1: Write the failing tests**

Add tests that:
- build retrieval, memory, ingest, and workflow services independently
- verify alternate injected factories/providers can be used without changing app startup behavior

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py -q
```

Expected: FAIL because runtime composition is still monolithic.

**Step 3: Write minimal implementation**

Refactor `build_runtime_services()` into:
- `build_retrieval_service(...)`
- `build_memory_service(...)`
- `build_ingest_service(...)`
- `build_workflow_service(...)`

Add a small runtime composition object that owns service lifecycle.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_checkpointing.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py src/base_agent_system/app_state.py src/base_agent_system/dependencies.py tests/integration/test_workflow.py
git commit -m "refactor: split runtime composition into factories"
```

### Task 3: Add Ingestion Connector Boundary

**Files:**
- Create: `src/base_agent_system/ingestion/connectors.py`
- Modify: `src/base_agent_system/ingestion/pipeline.py`
- Modify: `src/base_agent_system/ingestion/markdown_loader.py`
- Modify: `src/base_agent_system/ingestion/models.py`
- Test: `tests/integration/test_markdown_ingestion.py`
- Test: `tests/integration/test_ingestion_connectors.py`

**Step 1: Write the failing tests**

Add tests that:
- markdown ingestion works through a connector contract
- a fake connector can feed the same ingestion pipeline

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_markdown_ingestion.py tests/integration/test_ingestion_connectors.py -q
```

Expected: FAIL because the connector boundary does not exist yet.

**Step 3: Write minimal implementation**

Separate:
- document loading
- chunking/index refresh

Keep markdown as the only real built-in connector.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_markdown_ingestion.py tests/integration/test_ingestion_connectors.py tests/contract/test_ingest_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/ingestion tests/integration/test_markdown_ingestion.py tests/integration/test_ingestion_connectors.py tests/contract/test_ingest_api.py
git commit -m "feat: add ingestion connector boundary"
```

### Task 4: Add Retrieval Provider Boundary

**Files:**
- Create: `src/base_agent_system/retrieval/providers.py`
- Modify: `src/base_agent_system/retrieval/index_service.py`
- Modify: `src/base_agent_system/retrieval/models.py`
- Modify: `src/base_agent_system/workflow/nodes.py`
- Test: `tests/integration/test_retrieval.py`
- Test: `tests/integration/test_workflow.py`

**Step 1: Write the failing tests**

Add tests that:
- current local retrieval behavior still works through a provider contract
- workflow can run against a fake retrieval provider

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_retrieval.py tests/integration/test_workflow.py -q
```

Expected: FAIL because retrieval is still hardwired to one implementation.

**Step 3: Write minimal implementation**

Define a retrieval provider interface for:
- indexing/refresh
- query

Use current local retrieval index as the default implementation.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_retrieval.py tests/integration/test_workflow.py tests/contract/test_query_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/retrieval src/base_agent_system/workflow/nodes.py tests/integration/test_retrieval.py tests/integration/test_workflow.py tests/contract/test_query_api.py
git commit -m "feat: add retrieval provider boundary"
```

### Task 5: Add API Route Contributors

**Files:**
- Modify: `src/base_agent_system/api/app.py`
- Modify: `src/base_agent_system/api/routes_health.py`
- Modify: `src/base_agent_system/api/routes_ingest.py`
- Modify: `src/base_agent_system/api/routes_query.py`
- Test: `tests/integration/test_health_api.py`
- Test: `tests/contract/test_ingest_api.py`
- Test: `tests/contract/test_query_api.py`
- Test: `tests/integration/test_api_contributors.py`

**Step 1: Write the failing tests**

Add tests that:
- built-in routers are registered through contributors
- an extra fake contributor router is included in the app

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_api_contributors.py -q
```

Expected: FAIL because app assembly is still static.

**Step 3: Write minimal implementation**

Change app assembly so contributor objects return routers and the app includes them.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_api_contributors.py tests/integration/test_health_api.py tests/contract/test_ingest_api.py tests/contract/test_query_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/api tests/integration/test_api_contributors.py tests/integration/test_health_api.py tests/contract/test_ingest_api.py tests/contract/test_query_api.py
git commit -m "feat: add api route contributor model"
```

### Task 6: Add CLI Command Contributors

**Files:**
- Modify: `src/base_agent_system/cli/main.py`
- Modify: `src/base_agent_system/container.py`
- Test: `tests/smoke/test_cli.py`
- Test: `tests/integration/test_cli_contributors.py`

**Step 1: Write the failing tests**

Add tests that:
- built-in commands are registered through a contributor path
- a fake extra command can be added

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_cli_contributors.py tests/smoke/test_cli.py -q
```

Expected: FAIL because CLI registration is still static.

**Step 3: Write minimal implementation**

Move parser construction to a command contributor model with built-in defaults.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_cli_contributors.py tests/smoke/test_cli.py tests/smoke/test_container_contract.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/cli/main.py src/base_agent_system/container.py tests/integration/test_cli_contributors.py tests/smoke/test_cli.py tests/smoke/test_container_contract.py
git commit -m "feat: add cli command contributor model"
```

### Task 7: Add Constrained Workflow Hooks

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Modify: `src/base_agent_system/workflow/nodes.py`
- Modify: `src/base_agent_system/workflow/state.py`
- Test: `tests/integration/test_workflow.py`
- Test: `tests/integration/test_checkpointing.py`

**Step 1: Write the failing tests**

Add tests for one fake hook at each supported seam:
- before retrieval
- after retrieval
- before answer synthesis
- after answer synthesis

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_checkpointing.py -q
```

Expected: FAIL because workflow assembly has no constrained extension points.

**Step 3: Write minimal implementation**

Keep the current default graph, but express it as a constrained staged pipeline with limited hook insertion points.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_checkpointing.py tests/integration/test_end_to_end_query_flow.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow tests/integration/test_workflow.py tests/integration/test_checkpointing.py tests/integration/test_end_to_end_query_flow.py
git commit -m "feat: add constrained workflow hook points"
```

### Task 8: Document The Extension Model

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/troubleshooting.md`
- Test: `tests/smoke/test_extensibility_docs.py`

**Step 1: Write the failing test**

Add a smoke test asserting docs mention:
- supported extension seams
- explicit registration model
- one concrete extension example
- current non-goals:
  - no auto-discovery
  - no out-of-process plugins
  - no arbitrary workflow graph mutation

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_extensibility_docs.py -q
```

Expected: FAIL because the extension model is not documented yet.

**Step 3: Write minimal implementation**

Document:
- what can be extended
- how built-ins are registered
- one concrete example such as a new connector or extra CLI command
- what is intentionally not supported yet

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/smoke/test_extensibility_docs.py tests/smoke/test_kubernetes_runbooks.py tests/smoke/test_bootstrap_docs.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md docs/runbooks/troubleshooting.md tests/smoke/test_extensibility_docs.py
git commit -m "docs: describe extension model"
```

### Task 9: Full Verification For Extensibility Track

**Files:**
- Verify all changed files above

**Step 1: Run targeted suite**

```bash
python3 -m pytest tests/integration/test_extensions_registry.py tests/integration/test_ingestion_connectors.py tests/integration/test_api_contributors.py tests/integration/test_cli_contributors.py tests/integration/test_workflow.py tests/integration/test_retrieval.py tests/integration/test_checkpointing.py tests/integration/test_end_to_end_query_flow.py tests/contract/test_ingest_api.py tests/contract/test_query_api.py tests/smoke/test_cli.py tests/smoke/test_container_contract.py tests/smoke/test_extensibility_docs.py -q
```

Expected: PASS

**Step 2: Run broader suite**

```bash
python3 -m pytest tests -q
```

Expected: PASS

**Step 3: Manual sanity checks**

Run:

```bash
python3 -m base_agent_system.cli.main api
```

Then verify:
- `/live` returns `200`
- `/ready` returns `200`
- `/ingest` succeeds
- `/query` succeeds
- default behavior is unchanged with no custom registrations enabled

**Step 4: Commit if any final doc/test adjustments were needed**

```bash
git add .
git commit -m "test: verify extensibility baseline"
```

### Success Criteria

- The repo exposes explicit extension seams for workflows, ingestion, retrieval, API routes, and CLI commands.
- Built-in behavior still works as the default path with no custom registrations.
- Ingestion and retrieval are behind stable interfaces rather than hardwired implementations.
- API and CLI assembly support contributor registration.
- Workflow extension is limited to constrained hook points, not arbitrary graph mutation.
- Docs explain what is extendable, how to register built-ins/customizations, and what remains intentionally unsupported.

### Scope Guardrails

- No package entry-point discovery
- No generic plugin loading framework
- No event bus
- No multi-tenant redesign yet
- No provider orchestration overhaul yet
