# Base AI Agent System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python-first base AI agent system with FastAPI + CLI, Neo4j, Graphiti, LlamaIndex, LangGraph, Postgres checkpointing, local markdown ingestion, and Kubernetes-ready deployment.

**Architecture:** A single Python application owns API, CLI, ingestion, retrieval, memory integration, and workflow orchestration. Neo4j stores graph data, Graphiti provides temporal agent memory on top of it, Postgres stores LangGraph checkpoints, and FastAPI exposes a lightweight runtime API while CLI reuses the same internal services.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, LangGraph, langgraph-checkpoint-postgres, LlamaIndex, Graphiti, Neo4j, Postgres, Docker Compose, Kubernetes, Helm

---

### Task 1: Repository Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/base_agent_system/__init__.py`
- Create: `src/base_agent_system/config.py`
- Create: `src/base_agent_system/logging.py`
- Create: `tests/__init__.py`

**Step 1: Write the failing test**

Create a smoke import test:

```python
def test_package_imports():
    import base_agent_system
```

**Step 2: Run test to verify it fails**

Run: `pytest tests -q`
Expected: FAIL because package and project config do not exist

**Step 3: Write minimal implementation**

Add:
- Python project metadata
- runtime dependencies
- test dependencies
- package directory
- env example with placeholders for Neo4j, Postgres, provider keys

**Step 4: Run test to verify it passes**

Run: `pytest tests -q`
Expected: PASS for import smoke test

**Step 5: Commit**

```bash
git add pyproject.toml .env.example .gitignore README.md src/base_agent_system tests
git commit -m "feat: bootstrap Python application scaffold"
```

### Task 2: Local Infrastructure Scaffold

**Files:**
- Create: `infra/compose/docker-compose.yml`
- Create: `infra/compose/neo4j.env`
- Create: `infra/compose/postgres.env`
- Create: `docs/seed/README.md`

**Step 1: Write the failing test**

Add a smoke script or test expectation that required services are defined:
- `app`
- `neo4j`
- `postgres`

Example assertion in a test that reads compose YAML structure.

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_compose.py -q`
Expected: FAIL because compose file does not exist

**Step 3: Write minimal implementation**

Compose should define:
- `neo4j` with persistent volume, ports `7474` and `7687`, APOC enabled
- `postgres` with persistent volume and healthcheck
- optional `app` service for local containerized runs
- no separate Graphiti container in phase 1

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_compose.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add infra/compose docs/seed
git commit -m "feat: add local infrastructure scaffold"
```

### Task 3: Typed Configuration and App Wiring

**Files:**
- Modify: `src/base_agent_system/config.py`
- Create: `src/base_agent_system/app_state.py`
- Create: `src/base_agent_system/dependencies.py`

**Step 1: Write the failing test**

Test typed settings load required env vars and validate missing critical config.

```python
def test_settings_require_neo4j_and_postgres_urls():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_config.py -q`
Expected: FAIL because settings model is missing

**Step 3: Write minimal implementation**

Config should include:
- app env
- provider model names and API key names
- Neo4j URI/user/password/database
- Postgres URI
- docs seed path
- chunk size/overlap
- Graphiti telemetry toggle
- API port

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/config.py src/base_agent_system/app_state.py src/base_agent_system/dependencies.py tests/integration/test_config.py
git commit -m "feat: add typed runtime configuration"
```

### Task 4: Health Endpoints and FastAPI Lifespan

**Files:**
- Create: `src/base_agent_system/api/app.py`
- Create: `src/base_agent_system/api/routes_health.py`
- Create: `src/base_agent_system/api/models.py`

**Step 1: Write the failing test**

Add API tests:
- `GET /live` returns `200`
- `GET /ready` returns `503` when dependencies unavailable
- `GET /ready` returns `200` when dependencies initialize

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_health_api.py -q`
Expected: FAIL because API app does not exist

**Step 3: Write minimal implementation**

Implement:
- FastAPI app
- lifespan startup/shutdown
- `/live`
- `/ready`
- readiness based on initialized service handles

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_health_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/api tests/integration/test_health_api.py
git commit -m "feat: add FastAPI app with health endpoints"
```

### Task 5: CLI Entrypoint

**Files:**
- Create: `src/base_agent_system/cli/main.py`
- Update: `pyproject.toml`

**Step 1: Write the failing test**

Add CLI smoke tests for commands:
- `check-connections`
- `ingest`
- `ask`
- `smoke-test`

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_cli.py -q`
Expected: FAIL because CLI entrypoint is missing

**Step 3: Write minimal implementation**

Expose a console script, probably `base-agent-system`.
CLI should call shared services, not duplicate logic.

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_cli.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/cli pyproject.toml tests/smoke/test_cli.py
git commit -m "feat: add shared CLI entrypoint"
```

### Task 6: Markdown Ingestion Service

**Files:**
- Create: `src/base_agent_system/ingestion/markdown_loader.py`
- Create: `src/base_agent_system/ingestion/pipeline.py`
- Create: `src/base_agent_system/ingestion/models.py`
- Create: `tests/integration/test_markdown_ingestion.py`
- Create: `docs/seed/example.md`

**Step 1: Write the failing test**

Test that markdown files from `docs/seed/` are loaded and chunked with metadata.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_markdown_ingestion.py -q`
Expected: FAIL because loader/pipeline do not exist

**Step 3: Write minimal implementation**

Implement:
- local markdown file discovery
- document normalization
- LlamaIndex chunking pipeline
- metadata like file path and title

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_markdown_ingestion.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/ingestion tests/integration/test_markdown_ingestion.py docs/seed/example.md
git commit -m "feat: add local markdown ingestion pipeline"
```

### Task 7: Retrieval Service

**Files:**
- Create: `src/base_agent_system/retrieval/index_service.py`
- Create: `src/base_agent_system/retrieval/models.py`
- Create: `tests/integration/test_retrieval.py`

**Step 1: Write the failing test**

Test that ingested seed docs can be queried and return relevant chunks.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_retrieval.py -q`
Expected: FAIL because retrieval service does not exist

**Step 3: Write minimal implementation**

Implement a small retrieval adapter around LlamaIndex:
- build or load index
- query top-k chunks
- return citations with path and snippet

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_retrieval.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/retrieval tests/integration/test_retrieval.py
git commit -m "feat: add document retrieval service"
```

### Task 8: Graphiti Memory Integration

**Files:**
- Create: `src/base_agent_system/memory/graphiti_service.py`
- Create: `src/base_agent_system/memory/models.py`
- Create: `tests/integration/test_graphiti_memory.py`

**Step 1: Write the failing test**

Test that:
- a memory episode can be written
- relevant memory can be queried back
- service fails clearly if Neo4j or provider config is missing

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_graphiti_memory.py -q`
Expected: FAIL because memory service does not exist

**Step 3: Write minimal implementation**

Implement a narrow adapter:
- `initialize_indices()`
- `store_episode(...)`
- `search_memory(...)`

Keep Graphiti-specific details inside this module.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_graphiti_memory.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/memory tests/integration/test_graphiti_memory.py
git commit -m "feat: add Graphiti-backed memory adapter"
```

### Task 9: LangGraph State and Workflow

**Files:**
- Create: `src/base_agent_system/workflow/state.py`
- Create: `src/base_agent_system/workflow/graph.py`
- Create: `src/base_agent_system/workflow/nodes.py`
- Create: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

Add a workflow test that verifies the graph:
- retrieves docs
- retrieves memory
- produces an answer
- emits citations

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_workflow.py -q`
Expected: FAIL because workflow does not exist

**Step 3: Write minimal implementation**

State fields:
- `thread_id`
- `query`
- `retrieved_docs`
- `retrieved_memory`
- `answer`
- `citations`
- `debug`

Nodes:
- `retrieve_docs`
- `retrieve_memory`
- `synthesize_answer`
- `persist_memory`

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_workflow.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow tests/integration/test_workflow.py
git commit -m "feat: add LangGraph query workflow"
```

### Task 10: Postgres Checkpointing

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Create: `src/base_agent_system/checkpointing.py`
- Create: `tests/integration/test_checkpointing.py`

**Step 1: Write the failing test**

Test that graph state persists across requests by `thread_id`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_checkpointing.py -q`
Expected: FAIL because checkpointer is not configured

**Step 3: Write minimal implementation**

Use `langgraph-checkpoint-postgres`.
Important implementation details:
- initialize with proper connection settings
- call `.setup()` on first use
- compile workflow with the checkpointer once
- keep state small

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_checkpointing.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/checkpointing.py src/base_agent_system/workflow/graph.py tests/integration/test_checkpointing.py
git commit -m "feat: persist workflow state in Postgres"
```

### Task 11: Query API Contract

**Files:**
- Create: `src/base_agent_system/api/routes_query.py`
- Update: `src/base_agent_system/api/models.py`
- Create: `tests/contract/test_query_api.py`

**Step 1: Write the failing test**

Define the `POST /query` contract:

Request example:

```json
{
  "thread_id": "thread-123",
  "query": "What does the seed doc say?"
}
```

Response example:

```json
{
  "thread_id": "thread-123",
  "answer": "...",
  "citations": [
    {
      "source": "docs/seed/example.md",
      "snippet": "..."
    }
  ],
  "debug": {
    "memory_hits": 1,
    "document_hits": 2
  }
}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_query_api.py -q`
Expected: FAIL because route is missing

**Step 3: Write minimal implementation**

Implement `POST /query` using the shared workflow service.

**Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_query_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_query.py src/base_agent_system/api/models.py tests/contract/test_query_api.py
git commit -m "feat: add query endpoint with citations"
```

### Task 12: Ingest API Contract

**Files:**
- Create: `src/base_agent_system/api/routes_ingest.py`
- Create: `tests/contract/test_ingest_api.py`

**Step 1: Write the failing test**

Test a simple ingest endpoint:
- accepts a local path or defaults to `docs/seed`
- returns file count and chunk count

**Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_ingest_api.py -q`
Expected: FAIL because route is missing

**Step 3: Write minimal implementation**

Implement `POST /ingest` for admin/dev use only in phase 1.

**Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_ingest_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_ingest.py tests/contract/test_ingest_api.py
git commit -m "feat: add ingest endpoint for seed documents"
```

### Task 13: End-to-End Vertical Slice Test

**Files:**
- Create: `tests/integration/test_end_to_end_query_flow.py`

**Step 1: Write the failing test**

End-to-end test:
1. ingest seed docs
2. call `POST /query`
3. verify answer contains doc-backed info
4. ask follow-up in same `thread_id`
5. verify memory affects second response

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_end_to_end_query_flow.py -q`
Expected: FAIL because the full flow is not complete yet

**Step 3: Write minimal implementation**

Fix glue code only.
Do not add features beyond making the core flow work.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_end_to_end_query_flow.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/integration/test_end_to_end_query_flow.py
git commit -m "feat: complete first end-to-end agent slice"
```

### Task 14: Containerization

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `scripts/container-smoke.sh`
- Create: `tests/smoke/test_container_contract.py`

**Step 1: Write the failing test**

Test assumptions:
- app container exposes API port
- startup command is valid
- health endpoint is reachable in containerized mode

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_container_contract.py -q`
Expected: FAIL because Dockerfile is missing

**Step 3: Write minimal implementation**

Build one app image that supports:
- FastAPI runtime
- CLI invocation
- Kubernetes deployment

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_container_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add Dockerfile .dockerignore scripts/container-smoke.sh tests/smoke/test_container_contract.py
git commit -m "feat: add deployable application container"
```

### Task 15: Kubernetes Base Manifests

**Files:**
- Create: `infra/k8s/base/namespace.yaml`
- Create: `infra/k8s/base/configmap.yaml`
- Create: `infra/k8s/base/secret.example.yaml`
- Create: `infra/k8s/base/deployment.yaml`
- Create: `infra/k8s/base/service.yaml`
- Create: `infra/k8s/base/ingress.yaml`
- Create: `infra/k8s/base/kustomization.yaml`

**Step 1: Write the failing test**

Add manifest checks for:
- Deployment exists
- Service exists
- readiness/liveness probes use `/ready` and `/live`
- env config is wired

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_k8s_manifests.py -q`
Expected: FAIL because manifests do not exist

**Step 3: Write minimal implementation**

Create base manifests for the app only.
Include:
- rolling updates
- resource requests/limits
- probes
- env injection

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_k8s_manifests.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add infra/k8s/base tests/smoke/test_k8s_manifests.py
git commit -m "feat: add Kubernetes manifests for application service"
```

### Task 16: Neo4j Kubernetes Values

**Files:**
- Create: `infra/k8s/helm-values/neo4j.values.yaml`
- Create: `docs/deployment/neo4j.md`

**Step 1: Write the failing test**

Validate the values file includes:
- standalone deployment assumptions
- persistence
- auth
- APOC/plugin configuration as needed

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_neo4j_values.py -q`
Expected: FAIL because values file is missing

**Step 3: Write minimal implementation**

Prepare official Neo4j Helm values for self-hosted Kubernetes.
Phase 1 should target standalone, not clustered Neo4j.

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_neo4j_values.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add infra/k8s/helm-values/neo4j.values.yaml docs/deployment/neo4j.md tests/smoke/test_neo4j_values.py
git commit -m "feat: add Neo4j Helm configuration for Kubernetes"
```

### Task 17: Postgres Kubernetes Manifests

**Files:**
- Create: `infra/k8s/base/postgres-statefulset.yaml`
- Create: `infra/k8s/base/postgres-service.yaml`
- Update: `infra/k8s/base/kustomization.yaml`

**Step 1: Write the failing test**

Add a manifest test asserting Postgres resources exist for local cluster deployments.

**Step 2: Run test to verify it fails**

Run: `pytest tests/smoke/test_postgres_k8s.py -q`
Expected: FAIL because manifests are missing

**Step 3: Write minimal implementation**

Keep Postgres scoped to LangGraph checkpointing only.

**Step 4: Run test to verify it passes**

Run: `pytest tests/smoke/test_postgres_k8s.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add infra/k8s/base/postgres-statefulset.yaml infra/k8s/base/postgres-service.yaml infra/k8s/base/kustomization.yaml tests/smoke/test_postgres_k8s.py
git commit -m "feat: add Postgres manifests for checkpoint persistence"
```

### Task 18: Runbooks and Deployment Docs

**Files:**
- Create: `docs/runbooks/local-development.md`
- Create: `docs/runbooks/kubernetes-deployment.md`
- Create: `docs/runbooks/troubleshooting.md`

**Step 1: Write the failing test**

Add documentation smoke assertions if you want minimal presence checks, or skip tests and verify manually.

**Step 2: Run verification to confirm docs are needed**

Run:
- `pytest tests -q`
- manual review of startup, ingest, query, and k8s steps

**Step 3: Write minimal implementation**

Document:
- local startup
- env setup
- ingest flow
- query flow
- Neo4j/Postgres deployment order
- Kubernetes rollout and probe behavior
- common failures

**Step 4: Run verification**

Run:
- `pytest tests -q`
Expected: PASS
- manual docs sanity check

**Step 5: Commit**

```bash
git add docs/runbooks
git commit -m "docs: add local and Kubernetes runbooks"
```

### Final Verification

Run:

```bash
pytest tests -q
docker compose -f infra/compose/docker-compose.yml up -d
base-agent-system ingest docs/seed
base-agent-system ask "What is in the seed docs?"
```

Then verify:
- `GET /live` returns `200`
- `GET /ready` returns `200`
- `POST /query` returns `answer`, `citations`, `thread_id`, `debug`
- follow-up queries on same `thread_id` show memory continuity

### Notes For Execution

- Keep Graphiti embedded in the Python app for phase 1.
- Keep LangGraph state lean; do not store large raw documents in checkpoints.
- Reuse the same internal services from CLI and FastAPI.
- Start Neo4j as standalone in Kubernetes using official Helm charts.
- Do not add web ingestion, auth, or multi-agent orchestration in this first slice.

### Recommended Execution Order

1. Tasks 1-5
2. Tasks 6-10
3. Tasks 11-13
4. Tasks 14-18

### Execution Handoff

Plan complete and saved to `docs/plans/2026-04-06-base-ai-agent-system.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
