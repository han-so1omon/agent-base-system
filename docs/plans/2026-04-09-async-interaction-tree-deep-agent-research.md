# Async Interaction Tree And Deep-Agent Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current flat interaction record model with an event-sourced interaction tree that supports delegated `deep_agent` sub-interactions, ARQ-backed background execution, file-backed artifacts via storage abstraction, graph-first context retrieval, and schedule-triggered root interactions.

**Architecture:** Keep one interaction workflow, but let interactions exist at different depths in a strict tree. Canonical history lives in `interaction_events`; `interactions` stores cached current state for fast reads. Foreground HTTP requests and background ARQ workers both run the same workflow with different execution context. Threads become projections over root interactions plus selected child milestones.

**Tech Stack:** FastAPI, Postgres, ARQ, LangGraph/LangChain ReAct, Graphiti/Neo4j, Firecrawl, psycopg, Pydantic.

---

### Task 1: Define the target domain model in tests first

**Files:**
- Modify: `src/base_agent_system/interactions/models.py`
- Create: `tests/contract/test_interaction_models.py`

**Step 1: Write the failing tests**
- Add coverage for:
  - interaction identity without canonical `content`
  - `parent_interaction_id`
  - cached `status`, `last_event_at`, `latest_display_event_id`
  - `InteractionEvent`
  - `InteractionArtifactReference`
  - thread page payloads driven by event projections rather than row content

**Step 2: Run test to verify it fails**
- Run: `pytest tests/contract/test_interaction_models.py -q`
- Expected: FAIL with missing dataclasses/types

**Step 3: Write minimal implementation**
- Refactor `interactions/models.py` to introduce:
  - `Interaction`
  - `InteractionEvent`
  - `InteractionThreadSummary`
  - `InteractionPage`
  - `InteractionEventPage`
  - artifact reference/value objects
- Keep names generic, not research-specific

**Step 4: Run test to verify it passes**
- Run: `pytest tests/contract/test_interaction_models.py -q`

**Step 5: Commit**
- `git add tests/contract/test_interaction_models.py src/base_agent_system/interactions/models.py`
- `git commit -m "feat: add event-sourced interaction models"`

---

### Task 2: Redesign repository contract around interactions plus events

**Files:**
- Modify: `src/base_agent_system/interactions/repository.py`
- Modify: `tests/contract/test_interaction_repository.py`

**Step 1: Write the failing tests**
- Add tests for:
  - creating an interaction node
  - appending canonical events
  - updating cached interaction status on append
  - listing root interactions for a thread
  - listing child interactions by `parent_interaction_id`
  - listing event history for an interaction
  - projecting latest display event into thread responses
  - synthesized parent summary events after child completion/failure
  - cancellation request / acknowledged / completed event states

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_interaction_repository.py -q`

**Step 3: Write minimal implementation**
- Replace `interaction_records` model with repository methods roughly shaped like:
  - `create_interaction(...)`
  - `append_event(...)`
  - `list_thread_interactions(...)`
  - `list_child_interactions(...)`
  - `list_interaction_events(...)`
  - `request_cancellation(...)`
  - `has_thread(...)`
- Keep `InMemoryInteractionRepository` and `PostgresInteractionRepository` behavior aligned

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_interaction_repository.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/interactions/repository.py tests/contract/test_interaction_repository.py`
- `git commit -m "feat: add interaction event repository"`

---

### Task 3: Add Postgres schema for `interactions` and `interaction_events`

**Files:**
- Modify: `src/base_agent_system/interactions/repository.py`
- Possibly create: `src/base_agent_system/interactions/schema.py`
- Modify: `tests/contract/test_interaction_repository.py`

**Step 1: Write the failing tests**
- Assert schema initialization creates:
  - `interactions`
  - `interaction_events`
  - indexes for thread/root lookup, parent lookup, event timeline lookup
- Assert inserts/write paths target the new schema
- Assert JSON payloads are wrapped with `Jsonb`

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_interaction_repository.py -q`

**Step 3: Write minimal implementation**
- Add schema initialization SQL for:
  - `interactions`
  - `interaction_events`
- Preserve forward-only migration logic inside initialization for now
- Cache current-state fields on `interactions`

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_interaction_repository.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/interactions/repository.py tests/contract/test_interaction_repository.py`
- `git commit -m "feat: add interactions and interaction_events schema"`

---

### Task 4: Evolve API models to expose interaction tree projections

**Files:**
- Modify: `src/base_agent_system/api/models.py`
- Modify: `tests/contract/test_threads_api.py`

**Step 1: Write the failing tests**
- Add coverage for:
  - root interaction payloads without canonical row content
  - latest display event content/type
  - `status`
  - `parent_interaction_id`
  - projected child summary cards
  - optional child count / latest child milestone
  - separate event timeline payload for interaction detail view

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_threads_api.py -q`

**Step 3: Write minimal implementation**
- Introduce payloads for:
  - thread interaction summary
  - child interaction summary
  - interaction event payload
- Keep current thread route stable where possible, but make it projection-based

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_threads_api.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/api/models.py tests/contract/test_threads_api.py`
- `git commit -m "feat: add interaction tree api payloads"`

---

### Task 5: Add thread and interaction tree read endpoints

**Files:**
- Modify: `src/base_agent_system/api/routes_threads.py`
- Modify: `tests/contract/test_threads_api.py`

**Step 1: Write the failing tests**
- Add endpoints/tests for:
  - root interactions for a thread
  - children of an interaction
  - event history of an interaction
  - pagination on event history
  - milestone-only thread projection
  - debug route compatibility or replacement if debug becomes event-native

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_threads_api.py -q`

**Step 3: Write minimal implementation**
- Extend `routes_threads.py` with routes such as:
  - `GET /threads/{thread_id}/interactions`
  - `GET /interactions/{interaction_id}/children`
  - `GET /interactions/{interaction_id}/events`
- Keep route design generic; no research-specific endpoint names

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_threads_api.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/api/routes_threads.py tests/contract/test_threads_api.py`
- `git commit -m "feat: expose interaction tree read routes"`

---

### Task 6: Introduce storage abstraction for artifacts

**Files:**
- Create: `src/base_agent_system/artifacts/storage.py`
- Create: `src/base_agent_system/artifacts/models.py`
- Modify: `src/base_agent_system/config.py`
- Create: `tests/contract/test_artifact_storage.py`

**Step 1: Write the failing tests**
- Add tests for:
  - storage backend protocol
  - writing artifact bytes and returning a durable reference
  - resolving artifact references
  - metadata-only references in interaction events

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_artifact_storage.py -q`

**Step 3: Write minimal implementation**
- Define:
  - storage backend protocol
  - local/default storage implementation
  - artifact reference model
- Add config only for selecting backend/default local base path if needed
- Do not hardcode one location model into event schema

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_artifact_storage.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/artifacts src/base_agent_system/config.py tests/contract/test_artifact_storage.py`
- `git commit -m "feat: add artifact storage abstraction"`

---

### Task 7: Add schedule domain model and repository

**Files:**
- Create: `src/base_agent_system/scheduling/models.py`
- Create: `src/base_agent_system/scheduling/repository.py`
- Create: `tests/contract/test_schedule_repository.py`

**Step 1: Write the failing tests**
- Cover:
  - creating schedule definitions in Postgres
  - storing explicit context policy metadata
  - storing fresh-thread-per-run behavior
  - claiming due schedules
  - updating `next_run_at` / `last_run_at`
  - disabled schedules not being claimed

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_schedule_repository.py -q`

**Step 3: Write minimal implementation**
- Add generic schedule record support
- Keep schedule configuration out of the interaction tree

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_schedule_repository.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/scheduling tests/contract/test_schedule_repository.py`
- `git commit -m "feat: add schedule repository"`

---

### Task 8: Add async-capable interaction context object

**Files:**
- Create: `src/base_agent_system/workflow/context.py`
- Modify: `src/base_agent_system/workflow/state.py`
- Create: `tests/contract/test_workflow_context.py`

**Step 1: Write the failing tests**
- Cover an execution context carrying:
  - `thread_id`
  - `interaction_id`
  - `parent_interaction_id`
  - execution mode (`foreground` / `background`)
  - reporting target (`user` / `parent`)
  - context access policy
  - cancellation visibility

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_workflow_context.py -q`

**Step 3: Write minimal implementation**
- Add a generic workflow execution context object
- Avoid forking separate workflow classes

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_workflow_context.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/workflow/context.py src/base_agent_system/workflow/state.py tests/contract/test_workflow_context.py`
- `git commit -m "feat: add workflow execution context"`

---

### Task 9: Refactor memory service toward native async boundary

**Files:**
- Modify: `src/base_agent_system/memory/graphiti_service.py`
- Modify: `tests/integration/test_graphiti_memory.py`

**Step 1: Write the failing tests**
- Add tests for:
  - async methods on memory service/backend
  - compatibility adapter for sync callers during migration
  - cancellation-safe checkpoints around graph operations
  - Graphiti-backed calls using native async methods rather than hiding behind sync-only public service

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_graphiti_memory.py -q`

**Step 3: Write minimal implementation**
- Introduce async-first methods such as:
  - `ainitialize_indices`
  - `astore_episode`
  - `asearch_memory`
  - `aclose`
- Keep sync wrappers only where needed for migration
- Replace or isolate `_AsyncRunner` behind a narrower compatibility path

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_graphiti_memory.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/memory/graphiti_service.py tests/integration/test_graphiti_memory.py`
- `git commit -m "refactor: add async graphiti memory service"`

---

### Task 10: Add async Firecrawl client surface

**Files:**
- Modify: `src/base_agent_system/research/firecrawl_client.py`
- Modify: `tests/contract/test_firecrawl_client.py`
- Modify: `tests/contract/test_firecrawl_tools.py`

**Step 1: Write the failing tests**
- Add async client tests for:
  - scrape
  - search
  - crawl
  - crawl status
- Add tool tests for async-capable execution

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py -q`

**Step 3: Write minimal implementation**
- Introduce async methods and keep sync compatibility only if still needed during transition
- If no async HTTP dependency exists yet, plan for the smallest acceptable client addition or temporary thread wrapper isolated only in the client layer

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/research/firecrawl_client.py tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py`
- `git commit -m "refactor: add async firecrawl client"`

---

### Task 11: Add deep-agent spawn action to the ReAct workflow

**Files:**
- Modify: `src/base_agent_system/workflow/agent_tools.py`
- Modify: `src/base_agent_system/workflow/graph.py`
- Modify: `tests/contract/test_react_agent_tools.py`
- Modify: `tests/contract/test_react_agent_workflow.py`
- Modify: `tests/integration/test_workflow.py`

**Step 1: Write the failing tests**
- Cover:
  - spawn action/tool available to the agent
  - one spawn per foreground interaction
  - no recursive autonomous spawning in v1
  - structured spawned-child disclosure event, not hardcoded prose
  - same workflow path for top-level and child interactions
  - milestone-only parent projection

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_react_agent_tools.py tests/contract/test_react_agent_workflow.py tests/integration/test_workflow.py -q`

**Step 3: Write minimal implementation**
- Add a tool/action that creates a child interaction plus queue intent
- Extend workflow prompt with explicit delegation policy
- Ensure immediate response is structured around spawned child metadata

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_react_agent_tools.py tests/contract/test_react_agent_workflow.py tests/integration/test_workflow.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/workflow/agent_tools.py src/base_agent_system/workflow/graph.py tests/contract/test_react_agent_tools.py tests/contract/test_react_agent_workflow.py tests/integration/test_workflow.py`
- `git commit -m "feat: add deep-agent spawn action"`

---

### Task 12: Refactor `WorkflowService` to async-first execution

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/api/routes_interact.py`
- Modify: `src/base_agent_system/api/routes_chat.py`
- Modify: `tests/integration/test_graphiti_memory.py`
- Create: `tests/integration/test_async_workflow_service.py`

**Step 1: Write the failing tests**
- Cover:
  - `WorkflowService.arun(...)`
  - sync compatibility wrapper only where needed
  - interaction/event persistence on async path
  - foreground HTTP handlers awaiting workflow execution
  - child/background branch execution using same service

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_async_workflow_service.py tests/integration/test_graphiti_memory.py -q`

**Step 3: Write minimal implementation**
- Add `arun(...)` as primary API
- Migrate persistence methods to append interaction events instead of row content
- Update HTTP routes to `await` the workflow path
- Keep `run(...)` only as a temporary wrapper if needed

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_async_workflow_service.py tests/integration/test_graphiti_memory.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/runtime_services.py src/base_agent_system/api/routes_interact.py src/base_agent_system/api/routes_chat.py tests/integration/test_async_workflow_service.py tests/integration/test_graphiti_memory.py`
- `git commit -m "refactor: make workflow service async-first"`

---

### Task 13: Add ARQ worker integration for background child execution

**Files:**
- Create: `src/base_agent_system/workers/arq_worker.py`
- Create: `src/base_agent_system/workers/tasks.py`
- Modify: `src/base_agent_system/dependencies.py`
- Modify: `src/base_agent_system/app_state.py`
- Create: `tests/integration/test_arq_worker.py`

**Step 1: Write the failing tests**
- Cover:
  - enqueuing child interactions
  - worker loading runtime services
  - worker running same workflow against child branch
  - milestone event emission
  - parent summary synthesis on completion/failure
  - cooperative cancellation checks

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_arq_worker.py -q`

**Step 3: Write minimal implementation**
- Add ARQ job entrypoint for “run interaction branch”
- Pass interaction context, not research-specific job objects
- Ensure worker writes child canonical events and parent summary events

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_arq_worker.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/workers src/base_agent_system/dependencies.py src/base_agent_system/app_state.py tests/integration/test_arq_worker.py`
- `git commit -m "feat: add arq interaction worker"`

---

### Task 14: Add cancellation request flow

**Files:**
- Modify: `src/base_agent_system/api/routes_threads.py`
- Create: `src/base_agent_system/api/routes_interactions.py`
- Modify: `tests/contract/test_threads_api.py`
- Create: `tests/contract/test_interaction_cancellation_api.py`

**Step 1: Write the failing tests**
- Cover:
  - requesting cancellation on an interaction
  - marking interaction/event state as cancellation-requested
  - worker observing cancellation at checkpoints
  - final `cancelled` state when acknowledged

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_interaction_cancellation_api.py tests/contract/test_threads_api.py -q`

**Step 3: Write minimal implementation**
- Add a route like:
  - `POST /interactions/{interaction_id}/cancel`
- Implement repository methods and worker checks
- Keep cancellation cooperative

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_interaction_cancellation_api.py tests/contract/test_threads_api.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/api/routes_interactions.py src/base_agent_system/api/routes_threads.py tests/contract/test_interaction_cancellation_api.py tests/contract/test_threads_api.py`
- `git commit -m "feat: add interaction cancellation flow"`

---

### Task 15: Add schedule firing into fresh threads with context policy

**Files:**
- Create: `src/base_agent_system/scheduling/service.py`
- Create: `src/base_agent_system/workers/scheduler.py`
- Modify: `tests/contract/test_schedule_repository.py`
- Create: `tests/integration/test_schedule_execution.py`

**Step 1: Write the failing tests**
- Cover:
  - due schedule claim
  - fresh thread per run
  - root interaction creation from schedule
  - explicit context sources in metadata
  - graph-first retrieval policy stored on interaction metadata
  - enqueueing normal workflow execution

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_schedule_execution.py tests/contract/test_schedule_repository.py -q`

**Step 3: Write minimal implementation**
- Add schedule execution service that creates:
  - new thread id
  - root interaction
  - appropriate metadata/context policy
  - ARQ job enqueue
- Keep schedule execution generic, not research-only

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_schedule_execution.py tests/contract/test_schedule_repository.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/scheduling src/base_agent_system/workers/scheduler.py tests/integration/test_schedule_execution.py tests/contract/test_schedule_repository.py`
- `git commit -m "feat: add schedule-driven root interactions"`

---

### Task 16: Implement graph-first retrieval policy plumbing

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Modify: `src/base_agent_system/workflow/agent_tools.py`
- Modify: `src/base_agent_system/memory/graphiti_service.py`
- Create: `tests/integration/test_graph_first_retrieval.py`

**Step 1: Write the failing tests**
- Cover:
  - explicit context policy on interaction metadata
  - graph-first search from seeds
  - narrowing artifact/document retrieval by graph results
  - fallback widening only inside allowed envelope
  - no unrestricted all-thread search

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_graph_first_retrieval.py -q`

**Step 3: Write minimal implementation**
- Add retrieval orchestration order:
  - graph first
  - then artifacts/docs
- Keep backends pluggable for future stronger Neo4j/LlamaIndex integration

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_graph_first_retrieval.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/workflow/graph.py src/base_agent_system/workflow/agent_tools.py src/base_agent_system/memory/graphiti_service.py tests/integration/test_graph_first_retrieval.py`
- `git commit -m "feat: add graph-first interaction retrieval"`

---

### Task 17: Migrate chat/thread UI contracts to child-aware projections

**Files:**
- Modify: `tests/contract/test_chat_ui_api.py`
- Modify: `tests/contract/test_chat_ui_streaming.py`
- Modify: `tests/smoke/test_web_chat_app_layout.py`
- Possibly modify backend routes touched by those tests

**Step 1: Write the failing tests**
- Cover:
  - chat response carrying spawned child summary metadata
  - thread polling seeing milestone-only updates
  - expanded interaction detail fetching children/events
  - existing chat still working for simple foreground interactions

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/smoke/test_web_chat_app_layout.py -q`

**Step 3: Write minimal implementation**
- Keep current UI-compatible routes working
- Add only the minimal new response fields needed for sub-agent card rendering

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/smoke/test_web_chat_app_layout.py -q`

**Step 5: Commit**
- `git add tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/smoke/test_web_chat_app_layout.py`
- `git commit -m "feat: add sub-interaction thread projections"`

---

### Task 18: Wire configuration for ARQ and artifact storage

**Files:**
- Modify: `src/base_agent_system/config.py`
- Modify: `tests/integration/test_config.py`

**Step 1: Write the failing tests**
- Add config tests for:
  - ARQ/Redis connection settings
  - worker queue names if needed
  - artifact storage backend selection
  - local storage defaults
  - scheduler polling settings if needed

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_config.py -q`

**Step 3: Write minimal implementation**
- Extend `Settings` with only the config needed by chosen architecture
- Avoid speculative backend matrix

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_config.py -q`

**Step 5: Commit**
- `git add src/base_agent_system/config.py tests/integration/test_config.py`
- `git commit -m "feat: add arq and artifact storage config"`

---

### Task 19: Add integration tests for full delegated interaction lifecycle

**Files:**
- Create: `tests/integration/test_deep_agent_lifecycle.py`

**Step 1: Write the failing tests**
- Cover end-to-end:
  - user/root interaction enters system
  - ReAct chooses spawn
  - child interaction queued
  - worker starts and emits checkpoints
  - child completion creates parent summary event
  - thread projection shows milestones only
  - artifacts referenced from events
  - cancellation request stops child at checkpoint
  - failure path creates parent failure summary

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/integration/test_deep_agent_lifecycle.py -q`

**Step 3: Write minimal implementation**
- Fill only the missing gaps revealed by this E2E path
- Avoid broad refactors outside proven failures

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/integration/test_deep_agent_lifecycle.py -q`

**Step 5: Commit**
- `git add tests/integration/test_deep_agent_lifecycle.py`
- `git commit -m "test: cover delegated interaction lifecycle"`

---

### Task 20: Run focused and then broad verification

**Files:**
- No code changes expected

**Step 1: Run focused suites**
- Run:
  - `pytest tests/contract/test_interaction_models.py -q`
  - `pytest tests/contract/test_interaction_repository.py -q`
  - `pytest tests/contract/test_threads_api.py -q`
  - `pytest tests/integration/test_graphiti_memory.py -q`
  - `pytest tests/integration/test_workflow.py -q`
  - `pytest tests/integration/test_deep_agent_lifecycle.py -q`

**Step 2: Run broad suites**
- Run: `pytest -q`

**Step 3: Fix any failures**
- Apply the smallest correction necessary
- Re-run the failing tests, then the broad suite

**Step 4: Commit final stabilization**
- `git add <relevant files>`
- `git commit -m "refactor: unify interactions under async event tree"`

---

**Open points I would carry into execution, but not block on:**
- whether async Firecrawl should use a new HTTP dependency or a tightly isolated compatibility wrapper first
- exact ARQ Redis config names
- whether to preserve the current `/debug/...` route or replace it with event timeline detail
- whether thread preview generation should remain a separate LLM call or become derived from early root interaction events

**Recommended execution order adjustment**
- Do Tasks 1-5 first as the data/read model slice
- Then Tasks 8-13 as the async execution slice
- Then Tasks 6-7 and 15-18 for artifacts/scheduling/config
- End with Tasks 16, 17, 19, 20 for integration hardening
