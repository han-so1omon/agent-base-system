# Live Graphiti Runtime Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the normal application runtime use live Graphiti + Neo4j-backed memory so thread memory survives restarts and can be inspected in Neo4j Browser/Bloom.

**Architecture:** The current runtime hardcodes an in-memory Graphiti backend inside `build_runtime_services()`, which makes memory ephemeral and invisible to Neo4j inspection. The new design should use live Graphiti memory by default in normal runtime, and keep in-memory memory available only through explicit test injection. This preserves honest production behavior while keeping tests deterministic and fast.

**Tech Stack:** Python 3.11, FastAPI, Graphiti, Neo4j, LangGraph, pytest

---

### Task 1: Make Runtime Default To Live Graphiti Memory

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Test: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

Add a test proving the runtime builder does not inject `_InMemoryGraphitiBackend()` by default.

Example expectation:

```python
def test_build_runtime_services_prefers_live_graphiti_memory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    ...
```

The test should verify that normal runtime construction builds `GraphitiMemoryService` without the in-memory backend.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py -q
```

Expected: FAIL because `build_runtime_services()` still hardcodes `_InMemoryGraphitiBackend()`.

**Step 3: Write minimal implementation**

In `src/base_agent_system/runtime_services.py`:
- remove hardcoded `_InMemoryGraphitiBackend()` injection from `build_runtime_services()`
- construct `GraphitiMemoryService(settings=settings)` directly for normal runtime
- leave the in-memory backend class available for explicit test injection only

Do not add an in-memory runtime fallback branch.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/integration/test_workflow.py -q
```

Expected: PASS

### Task 2: Add Explicit Test-Only Memory Backend Injection

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/dependencies.py`
- Possibly modify: `src/base_agent_system/api/app.py`
- Test: `tests/integration/test_end_to_end_query_flow.py`
- Test: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

Add a test proving tests can still opt into in-memory memory explicitly while normal runtime remains live.

Example intent:

```python
def test_end_to_end_query_flow_can_use_explicit_in_memory_backend_for_tests():
    ...
```

The test should pass an explicit in-memory backend into runtime construction and verify the current query-memory behavior remains deterministic.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_end_to_end_query_flow.py -q
```

Expected: FAIL because current tests depend on runtime defaulting to in-memory memory.

**Step 3: Write minimal implementation**

Add the smallest possible test seam:
- allow `build_runtime_services(...)` to accept an optional memory backend override
- allow `create_app_state(...)` to pass that override through when needed by tests
- only tests should provide `_InMemoryGraphitiBackend()`

Keep normal runtime construction unchanged beyond using live Graphiti by default.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/integration/test_end_to_end_query_flow.py tests/integration/test_workflow.py -q
```

Expected: PASS

### Task 3: Add Tests That Prove Runtime Selection Is Honest

**Files:**
- Modify: `tests/integration/test_graphiti_memory.py`
- Possibly modify: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

Add tests proving:
- normal runtime uses live Graphiti memory service wiring
- explicit injected in-memory backend still works in tests
- no implicit runtime fallback exists

Example expectations:

```python
def test_runtime_memory_selection_defaults_to_live_graphiti(...):
    ...

def test_runtime_memory_selection_uses_injected_backend_for_tests(...):
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_graphiti_memory.py -q
```

Expected: FAIL because runtime still defaults to in-memory memory.

**Step 3: Write minimal implementation**

Adjust runtime and/or test seams so these tests can observe the actual backend selection path.

Do not introduce a production fallback env var.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/integration/test_graphiti_memory.py -q
```

Expected: PASS

### Task 4: Preserve Manual Validation Through Documentation

**Files:**
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/troubleshooting.md`
- Possibly modify: `README.md`

**Step 1: Inspect current docs**

Confirm they do not yet explain:
- live Graphiti provider requirements
- why memory was previously invisible in Neo4j
- how to validate restart persistence

**Step 2: Write minimal documentation updates**

Document:
- required env vars for live Graphiti runtime
- exact smoke test sequence:
  - ingest docs
  - store thread memory
  - query thread memory
  - restart API
  - query again
  - inspect Neo4j Browser for the thread
- troubleshooting note:
  - if memory disappears after restart and Neo4j is empty, runtime is not using live persistent memory

**Step 3: Verify docs against reality**

Run the documented manual sequence after implementation and confirm the docs match the observed behavior.

Expected: docs accurately describe the live runtime path.

### Task 5: Full Verification

**Files:**
- Verify all changed runtime, tests, and docs

**Step 1: Run focused tests**

```bash
python3 -m pytest tests/integration/test_workflow.py tests/integration/test_end_to_end_query_flow.py tests/integration/test_graphiti_memory.py -q
```

Expected: PASS

**Step 2: Run full suite**

```bash
python3 -m pytest tests -q
```

Expected: PASS

**Step 3: Run manual live smoke test**

With real env vars:

```bash
export BASE_AGENT_SYSTEM_NEO4J_URI=bolt://localhost:7687
export BASE_AGENT_SYSTEM_NEO4J_USER=neo4j
export BASE_AGENT_SYSTEM_NEO4J_PASSWORD=password
export BASE_AGENT_SYSTEM_NEO4J_DATABASE=neo4j
export BASE_AGENT_SYSTEM_POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/app
export OPENAI_API_KEY=...
python3 -m uvicorn base_agent_system.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then:
- ingest docs
- store memory in `smoke-thread`
- query memory
- restart API
- query memory again
- inspect Neo4j Browser with:

```cypher
MATCH (n)
WHERE n.group_id = "smoke-thread"
RETURN n
LIMIT 25;
```

Expected:
- memory survives restart
- Neo4j Browser shows persisted thread-linked graph memory

### Success Criteria

- normal runtime uses live Graphiti memory
- memory survives API restart
- Neo4j Browser/Bloom can inspect runtime thread memory
- tests remain deterministic through explicit test injection only
- no in-memory fallback exists in normal runtime
