# Interact Endpoint Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `/query` with a canonical `/interact` endpoint that accepts `messages` only, and make `/api/chat` a thin UI adapter over the same backend interaction path so both APIs share identical agent behavior.

**Architecture:** Introduce `/interact` as the sole backend interaction contract for agent execution. Keep `/api/chat` as a transport adapter for the web UI by translating AI SDK chat payloads into the `/interact` message format and reformatting the response for JSON chat mode or text streaming. Remove `/query` entirely in the same change rather than carrying compatibility aliases.

**Tech Stack:** FastAPI, Pydantic, LangGraph, LangChain OpenAI, Graphiti, pytest, Next.js, Helm, kind.

---

### Task 1: Add the canonical `/interact` API contract

**Files:**
- Create: `src/base_agent_system/api/routes_interact.py`
- Modify: `src/base_agent_system/api/models.py`
- Test: `tests/contract/test_interact_api.py`

**Step 1: Write the failing test**

Create `tests/contract/test_interact_api.py` covering the new canonical request and response contract.

Test shape to add:

```python
def test_post_interact_returns_answer_citations_thread_id_and_debug(...):
    response = client.post(
        "/interact",
        json={
            "thread_id": "thread-123",
            "messages": [{"role": "user", "content": "What does the seed doc say?"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["thread_id"] == "thread-123"
    assert response.json()["citations"]
```

Add one validation test proving `messages=[]` or missing text returns `400` or model validation failure, depending on the chosen route contract.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_interact_api.py -q`

Expected: FAIL because `/interact` does not exist yet.

**Step 3: Write minimal implementation**

- Add `InteractRequest` and `InteractResponse` models in `src/base_agent_system/api/models.py`
- `InteractRequest` should accept:
  - `thread_id: str`
  - `messages: list[InteractMessage]`
- Keep `InteractMessage` minimal:
  - `role: str`
  - `content: str`
- Add `src/base_agent_system/api/routes_interact.py`
- Route handler should:
  - read `workflow_service`
  - call `workflow_service.run(thread_id=payload.thread_id, messages=[...])`
  - return `InteractResponse.model_validate(result)`
- Do not add `query` compatibility

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_interact_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/models.py src/base_agent_system/api/routes_interact.py tests/contract/test_interact_api.py
git commit -m "feat: add canonical interact endpoint"
```

### Task 2: Make `/api/chat` a wrapper over the canonical interaction path

**Files:**
- Modify: `src/base_agent_system/api/routes_chat.py`
- Test: `tests/contract/test_chat_ui_api.py`
- Test: `tests/contract/test_chat_ui_streaming.py`

**Step 1: Write the failing test**

Update chat contract tests so they prove `/api/chat` delegates through the canonical interaction path instead of owning distinct request semantics.

Recommended test signal:

```python
assert normalized_messages == [
    {"role": "user", "content": "First question"},
    {"role": "assistant", "content": "First answer"},
    {"role": "user", "content": "Follow-up"},
]
```

Add or adjust one test that proves stream mode still returns:
- `Content-Type: text/plain`
- `X-Thread-Id`
- `X-Citations`
- `X-Debug`

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

Expected: FAIL once the tests are updated to assert the new shared interaction path behavior.

**Step 3: Write minimal implementation**

- Add a small shared helper used by both routes, for example in `routes_interact.py` or `routes_chat.py`
- The shared helper should accept:
  - `workflow_service`
  - `thread_id`
  - normalized `messages`
- It should call `workflow_service.run(...)` exactly once and return the canonical result envelope
- Update `/api/chat` to:
  - normalize UI messages
  - delegate to that shared helper
  - keep only response formatting responsibilities
- Do not implement an actual HTTP self-call from `/api/chat` to `/interact`; use shared Python code instead

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_chat.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py
git commit -m "refactor: route chat through interact adapter"
```

### Task 3: Remove `/query` entirely and switch registry wiring to `/interact`

**Files:**
- Delete: `src/base_agent_system/api/routes_query.py`
- Modify: `src/base_agent_system/extensions/registry.py`
- Test: `tests/integration/test_api_contributors.py`
- Test: `tests/contract/test_query_api.py`

**Step 1: Write the failing test**

Replace the `/query` contract test with an assertion that `/query` is gone and `/interact` is registered.

Examples:

```python
def test_post_query_is_not_available(...):
    response = client.post("/query", json={...})
    assert response.status_code == 404

def test_post_interact_is_available(...):
    response = client.post("/interact", json={...})
    assert response.status_code == 200
```

If it is clearer, rename `tests/contract/test_query_api.py` to `tests/contract/test_interact_api.py` and remove the old file entirely.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/contract/test_query_api.py tests/integration/test_api_contributors.py -q
```

Expected: FAIL because `/query` is still registered.

**Step 3: Write minimal implementation**

- Remove the `/query` router contributor from the default registry
- Register the `/interact` router contributor instead
- Delete `routes_query.py`
- Rename tests if needed so the repo no longer treats `/query` as a supported API
- Do not leave redirects or aliases

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/contract/test_interact_api.py tests/integration/test_api_contributors.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/extensions/registry.py src/base_agent_system/api/routes_interact.py tests/contract/test_interact_api.py tests/integration/test_api_contributors.py
git rm src/base_agent_system/api/routes_query.py tests/contract/test_query_api.py
git commit -m "refactor: replace query endpoint with interact"
```

### Task 4: Migrate integration and end-to-end tests from `/query` to `/interact`

**Files:**
- Modify: `tests/integration/test_end_to_end_query_flow.py`
- Modify: `tests/integration/test_workflow.py`
- Modify: `tests/smoke/test_kubernetes_runbooks.py`
- Modify: any remaining test files returned by `rg '/query' tests`

**Step 1: Write the failing test**

Update end-to-end and smoke tests so they use `/interact` and message payloads only.

Example replacement payload:

```python
response = client.post(
    "/interact",
    json={
        "thread_id": "thread-e2e",
        "messages": [{"role": "user", "content": "What does the markdown ingestion service do?"}],
    },
)
```

Keep thread continuity across follow-up calls by reusing the same `thread_id`.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/integration/test_end_to_end_query_flow.py tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: FAIL because docs and tests still mention `/query`.

**Step 3: Write minimal implementation**

- Update all integration and smoke tests from `/query` to `/interact`
- Use `messages` payloads everywhere
- Preserve expectations around:
  - citations
  - debug counters
  - thread memory persistence
- Do not change unrelated retrieval or memory assertions

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/integration/test_end_to_end_query_flow.py tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/integration/test_end_to_end_query_flow.py tests/integration/test_workflow.py tests/smoke/test_kubernetes_runbooks.py
git commit -m "test: migrate api callers to interact endpoint"
```

### Task 5: Update docs and operator guidance from `/query` to `/interact`

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Modify: any additional docs returned by `rg '/query' docs README.md`

**Step 1: Write the failing test**

Update the runbook smoke test and any doc assertions so they require `/interact` and no longer require `/query`.

Example expectations:

```python
assert "/interact" in text
assert "/query" not in text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: FAIL because docs still mention `/query`.

**Step 3: Write minimal implementation**

- Replace `/query` usage examples with `/interact`
- Update request examples to use `messages`
- Clarify that:
  - `/interact` is the canonical backend API
  - `/api/chat` is the UI adapter for the packaged web chat
- Remove any wording that implies `/query` is still supported

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md docs/runbooks/kubernetes-deployment.md tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: replace query api with interact"
```

### Task 6: Run full verification and redeploy to kind

**Files:**
- Verify only: all files changed in Tasks 1-5

**Step 1: Run targeted verification**

Run:

```bash
python3 -m pytest tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/integration/test_api_contributors.py tests/integration/test_end_to_end_query_flow.py tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
python3 -m pytest tests -q
```

Expected: PASS.

**Step 3: Rebuild and redeploy to kind**

Run:

```bash
rtk docker build -t base-agent-system:0.1.0 .
kind load docker-image base-agent-system:0.1.0 --name base-agent-system
rtk helm upgrade --install base-agent-system infra/helm/base-agent-system -n base-agent-system --values infra/helm/environments/kind/values.yaml --values infra/helm/environments/kind/values.local.yaml
rtk kubectl rollout restart deployment/base-agent-system -n base-agent-system
rtk kubectl rollout status deployment/base-agent-system -n base-agent-system --timeout=180s
```

Expected: successful rollout.

**Step 4: Run live smoke checks**

Run:

```bash
rtk curl -i http://127.0.0.1:8000/live
rtk curl -i http://127.0.0.1:8000/ready
rtk curl -i http://127.0.0.1:8000/chat
rtk curl -i -H "Content-Type: application/json" --data-binary '{"thread_id":"smoke-interact","messages":[{"role":"user","content":"What does the seed document explain?"}]}' http://127.0.0.1:8000/interact
rtk curl -i -H "Accept: text/plain" -H "Content-Type: application/json" --data-binary '{"threadId":"smoke-chat","messages":[{"role":"user","content":"What does the seed document explain?"}]}' http://127.0.0.1:8000/api/chat
rtk curl -i -H "Content-Type: application/json" --data-binary '{"thread_id":"smoke-query","query":"test"}' http://127.0.0.1:8000/query
```

Expected:
- `/live` -> `200`
- `/ready` -> `200`
- `/chat` -> `200`
- `/interact` -> `200` with grounded response payload
- `/api/chat` -> `200` with JSON or text/plain streaming response, depending on `Accept`
- `/query` -> `404`

**Step 5: Commit**

```bash
git add .
git commit -m "refactor: unify interaction api behind interact endpoint"
```

---

Plan complete and saved to `docs/plans/2026-04-08-interact-endpoint-unification.md`.

Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
