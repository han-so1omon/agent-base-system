# Interaction Threads UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add read-only interaction thread management to the backend and UI so operators can list threads, open a thread, load the most recent interactions first, page older interactions while scrolling upward, and continue an existing thread, while preserving LangGraph `thread_id` continuity and keeping chain-of-thought accessible only through debug-only endpoints.

**Architecture:** Keep LangGraph as the execution/resume layer keyed by `thread_id`, keep Graphiti `MemoryEpisode` as semantic memory for retrieval, and add a separate Postgres-backed interaction read/write model for UI threads. Public APIs should expose thread summaries and visible interactions only, while an internal/debug API exposes normalized run steps and stored intermediate reasoning when an explicit config flag enables it.

**Tech Stack:** FastAPI, Postgres, psycopg, LangGraph, Graphiti, pytest, Next.js, Vercel AI SDK, kind/Helm.

---

### Task 1: Add interaction thread configuration and Postgres repository boundary

**Files:**
- Modify: `src/base_agent_system/config.py`
- Create: `src/base_agent_system/interactions/models.py`
- Create: `src/base_agent_system/interactions/repository.py`
- Test: `tests/integration/test_config.py`
- Test: `tests/contract/test_interaction_repository.py`

**Step 1: Write the failing tests**

Add config coverage for the new thread/debug settings and add repository contract tests for the transcript storage boundary.

Add config expectations like:

```python
settings = load_settings()
assert settings.debug_interactions_enabled is False
assert settings.interactions_page_size == 20
```

Add repository tests proving a repository can:

```python
repository = PostgresInteractionRepository(connection_factory=fake_connection)
repository.initialize_schema()
repository.store_user_interaction(...)
repository.store_agent_run_interaction(...)
threads = repository.list_threads(limit=50)
page = repository.list_interactions(thread_id="thread-123", limit=20)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/integration/test_config.py tests/contract/test_interaction_repository.py -q
```

Expected: FAIL because the config fields and interaction repository do not exist.

**Step 3: Write minimal implementation**

- Add config fields:
  - `debug_interactions_enabled: bool = False`
  - `interactions_page_size: int = 20`
- Create interaction domain models for:
  - `InteractionThreadSummary`
  - `Interaction`
  - `AgentRunMetadata`
  - `InteractionPage`
  - internal run-step and reasoning records
- Create a Postgres repository boundary with methods for:
  - schema initialization
  - storing user interactions
  - storing agent-run interactions
  - listing recent threads
  - listing visible interactions by cursor
  - fetching debug details for one interaction
- Keep this boundary transcript-oriented, separate from `MemoryEpisode`

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_config.py tests/contract/test_interaction_repository.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/config.py src/base_agent_system/interactions/models.py src/base_agent_system/interactions/repository.py tests/integration/test_config.py tests/contract/test_interaction_repository.py
git commit -m "feat: add interaction thread repository boundary"
```

### Task 2: Persist visible interactions, steps, and internal reasoning after agent runs

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/workflow/graph.py`
- Modify: `src/base_agent_system/workflow/state.py`
- Test: `tests/integration/test_workflow.py`
- Test: `tests/integration/test_graphiti_memory.py`
- Test: `tests/contract/test_react_agent_workflow.py`

**Step 1: Write the failing tests**

Add tests proving that after an interaction:

```python
result = workflow_service.run(thread_id="thread-123", messages=[...])
assert interaction_repository.list_threads(limit=10)[0].thread_id == "thread-123"
assert interaction_repository.list_interactions(thread_id="thread-123", limit=20).items[-1].kind == "agent_run"
assert interaction_repository.get_debug_interaction(...).reasoning is not None
```

Add a workflow-level contract test that the agent result envelope includes enough run metadata to persist:
- final visible answer
- tool names used
- tool call count
- normalized steps
- intermediate reasoning payload when available

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_graphiti_memory.py tests/contract/test_react_agent_workflow.py -q
```

Expected: FAIL because interaction persistence does not exist and the workflow result does not yet carry structured run details.

**Step 3: Write minimal implementation**

- Extend the workflow result shape to carry structured run metadata in addition to `answer`, `citations`, and `debug`
- Capture:
  - `used_tools`
  - `tool_call_count`
  - `tools_used`
  - normalized `steps`
  - internal `intermediate_reasoning`
- Add an interaction repository dependency into `WorkflowService`
- After each run, persist:
  - one `user` interaction
  - one `agent_run` interaction with final visible response text
  - run steps
  - internal reasoning payload
- Keep `MemoryEpisode` persistence unchanged for semantic memory

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_graphiti_memory.py tests/contract/test_react_agent_workflow.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py src/base_agent_system/workflow/graph.py src/base_agent_system/workflow/state.py tests/integration/test_workflow.py tests/integration/test_graphiti_memory.py tests/contract/test_react_agent_workflow.py
git commit -m "feat: persist interaction runs and debug details"
```

### Task 3: Add public thread APIs and the debug-only interaction detail endpoint

**Files:**
- Create: `src/base_agent_system/api/routes_threads.py`
- Modify: `src/base_agent_system/api/models.py`
- Modify: `src/base_agent_system/extensions/registry.py`
- Test: `tests/contract/test_threads_api.py`
- Test: `tests/integration/test_api_contributors.py`

**Step 1: Write the failing tests**

Create thread API tests covering:

```python
response = client.get("/threads?limit=50")
assert response.status_code == 200
assert response.json()[0]["thread_id"] == "thread-123"
assert "preview" in response.json()[0]
```

Create interaction page tests covering:

```python
response = client.get("/threads/thread-123/interactions?limit=20")
assert response.status_code == 200
assert response.json()["messages"][0]["kind"] in {"user", "agent_run"}
assert "used_tools" in response.json()["messages"][0]["metadata"]
```

Create debug endpoint tests covering:

```python
response = client.get("/debug/threads/thread-123/interactions/interaction-1")
assert response.status_code == 404  # default-disabled
```

and a config-enabled case returning steps and reasoning.

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/contract/test_threads_api.py tests/integration/test_api_contributors.py -q
```

Expected: FAIL because the routes are not registered yet.

**Step 3: Write minimal implementation**

- Add public endpoints:
  - `GET /threads`
  - `GET /threads/{thread_id}/interactions`
- Add internal/debug endpoint:
  - `GET /debug/threads/{thread_id}/interactions/{interaction_id}`
- Default the debug endpoint to hidden/disabled when `debug_interactions_enabled` is false
- Keep public payloads visible-only:
  - `thread_id`
  - `preview`
  - visible interactions with `kind`, `content`, `created_at`, and agent-run badge metadata
- Do not expose `intermediate_reasoning` in public responses

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/contract/test_threads_api.py tests/integration/test_api_contributors.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_threads.py src/base_agent_system/api/models.py src/base_agent_system/extensions/registry.py tests/contract/test_threads_api.py tests/integration/test_api_contributors.py
git commit -m "feat: add thread list and interaction history apis"
```

### Task 4: Wire runtime service construction to initialize the interaction repository

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/api/app.py`
- Test: `tests/integration/test_workflow.py`
- Test: `tests/integration/test_checkpointing.py`

**Step 1: Write the failing tests**

Add runtime integration tests proving the app/runtime state now initializes the interaction repository and keeps the existing checkpointing path intact.

Example expectations:

```python
ingest_service, workflow_service = build_runtime_services(settings, ...)
assert workflow_service is not None
assert runtime_state.interaction_repository is not None
```

And preserve the current checkpoint compile path behavior.

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_checkpointing.py -q
```

Expected: FAIL because runtime state does not yet build/store the interaction repository.

**Step 3: Write minimal implementation**

- Initialize the interaction repository during runtime setup
- Ensure schema initialization happens once at startup
- Store the repository on application/runtime state so routes can access it
- Keep checkpointing and retrieval/memory initialization unchanged except for the new repository dependency

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_checkpointing.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py src/base_agent_system/api/app.py tests/integration/test_workflow.py tests/integration/test_checkpointing.py
git commit -m "feat: initialize interaction repository in runtime"
```

### Task 5: Add thread sidebar and paged interaction loading to the UI

**Files:**
- Modify: `web/app/page.tsx`
- Test: `tests/smoke/test_web_chat_app_layout.py`
- Test: `tests/contract/test_chat_ui_api.py`
- Test: `tests/contract/test_chat_ui_streaming.py`

**Step 1: Write the failing tests**

Update UI smoke coverage so it expects a thread sidebar and thread-loading UX instead of manual primary thread entry.

Example expectations:

```python
assert "Recent Threads" in html
assert "New thread starts on first message" in html
```

Add UI adapter tests as needed to preserve `/api/chat` transport compatibility while the page starts using `/threads` and `/threads/{thread_id}/interactions` for browsing.

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/smoke/test_web_chat_app_layout.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

Expected: FAIL because the page still uses a manual thread-id field as the primary UX and does not load thread history.

**Step 3: Write minimal implementation**

- Add a sidebar listing recent threads from `GET /threads`
- Remove the manual thread-id field as the main interaction control
- If there is no active thread and the operator sends a message, generate a new client-side `thread_id`
- When a thread is selected, fetch the most recent `N` interactions from `GET /threads/{thread_id}/interactions`
- Render:
  - `user` interactions
  - `agent_run` interactions
  - a simple visible tool-use badge based on `used_tools`, `tool_call_count`, and `tools_used`
- Implement upward pagination so older interactions load when scrolling up
- Keep `/api/chat` as the write/stream path for sending new messages

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/smoke/test_web_chat_app_layout.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add web/app/page.tsx tests/smoke/test_web_chat_app_layout.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py
git commit -m "feat: add thread sidebar and paged interaction view"
```

### Task 6: Document the new interaction thread APIs and debug policy

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Test: `tests/smoke/test_kubernetes_runbooks.py`

**Step 1: Write the failing test**

Update the runbook smoke test so it expects references to:
- `/threads`
- `/threads/{thread_id}/interactions`
- debug endpoint disabled by default

Example expectations:

```python
assert "/threads" in text
assert "/debug/threads/" in text
assert "disabled in production by default" in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: FAIL because docs do not yet describe thread APIs or the debug endpoint policy.

**Step 3: Write minimal implementation**

- Document the public thread APIs
- Document the thread sidebar behavior and automatic new-thread-on-first-message UX
- Document that debug interaction details are disabled in production by default and require explicit config to enable
- Keep docs aligned with `/interact` as the canonical execution API

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md docs/runbooks/kubernetes-deployment.md tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: add interaction thread api guidance"
```

### Task 7: Run full verification and redeploy to kind

**Files:**
- Verify only: all files changed in Tasks 1-6

**Step 1: Run targeted verification**

Run:

```bash
python3 -m pytest tests/contract/test_interaction_repository.py tests/contract/test_threads_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/integration/test_workflow.py tests/integration/test_checkpointing.py tests/integration/test_graphiti_memory.py tests/smoke/test_web_chat_app_layout.py tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
python3 -m pytest tests -q
```

Expected: PASS.

**Step 3: Redeploy to kind**

Run:

```bash
./scripts/deploy-kind.sh
```

Expected: successful rollout with a fresh kind-specific image tag.

**Step 4: Run live smoke checks**

Run:

```bash
rtk curl -i http://127.0.0.1:8000/live
rtk curl -i http://127.0.0.1:8000/chat
rtk curl -i http://127.0.0.1:8000/threads
rtk curl -i "http://127.0.0.1:8000/threads/<thread_id>/interactions?limit=20"
rtk curl -i -H "Content-Type: application/json" --data-binary '{"thread_id":"threads-smoke","messages":[{"role":"user","content":"What does the seed document explain?"}]}' http://127.0.0.1:8000/interact
```

Expected:
- `/live` -> `200`
- `/chat` -> `200`
- `/threads` -> `200`
- `/threads/{thread_id}/interactions` -> `200`
- `/interact` -> `200`
- UI shows a recent thread sidebar, loads recent interactions, and continues the same thread on subsequent sends

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add interaction threads and paged ui history"
```
