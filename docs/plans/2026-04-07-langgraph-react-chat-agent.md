# LangGraph ReAct Chat Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the synthetic backend chat answer path with a backend-owned LangGraph ReAct agent that uses `openai/gpt-4o-mini` through Vercel AI Gateway, dynamically decides when to call retrieval and memory tools, and streams real assistant responses to the packaged web chat UI.

**Architecture:** Keep FastAPI as the transport layer and preserve the existing retrieval index, Graphiti memory, and Postgres checkpointer. Replace the current query-centric synthesis node with a message-centric prebuilt LangGraph ReAct agent that uses two backend tools: one for document retrieval and one for thread memory lookup. The web app should switch from manual JSON fetches to AI SDK `useChat`, while the backend exposes a streaming `/api/chat` route that remains the system of record.

**Tech Stack:** FastAPI, LangGraph, LangChain, LangChain OpenAI, Vercel AI Gateway, Vercel AI SDK, Graphiti, Postgres, pytest, Next.js.

---

### Task 1: Add backend agent dependencies and runtime config

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/base_agent_system/config.py`
- Test: `tests/smoke/test_container_contract.py`

**Step 1: Write the failing test**

Extend `tests/smoke/test_container_contract.py` to assert the project dependencies and config contract now include the backend agent pieces and gateway settings:

```python
assert "langchain" in pyproject_text
assert "langchain-openai" in pyproject_text
assert "BASE_AGENT_SYSTEM_LLM_MODEL" in config_text
assert "BASE_AGENT_SYSTEM_AI_GATEWAY_API_KEY_NAME" in config_text
assert "BASE_AGENT_SYSTEM_AI_GATEWAY_BASE_URL" in config_text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_container_contract.py -q`

Expected: FAIL because the dependency strings and config keys do not exist yet.

**Step 3: Write minimal implementation**

- Add `langchain` and `langchain-openai` to `pyproject.toml`
- Add backend LLM config to `Settings`, loaded from env:
  - `BASE_AGENT_SYSTEM_LLM_MODEL` defaulting to `openai/gpt-4o-mini`
  - `BASE_AGENT_SYSTEM_AI_GATEWAY_API_KEY_NAME` defaulting to `AI_GATEWAY_API_KEY`
  - `BASE_AGENT_SYSTEM_AI_GATEWAY_BASE_URL` defaulting to `https://ai-gateway.vercel.sh/v1`
- Keep existing OpenAI/Anthropic env fields only if still needed elsewhere; do not add duplicate runtime concepts if they become unused.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_container_contract.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml src/base_agent_system/config.py tests/smoke/test_container_contract.py
git commit -m "feat: add backend agent runtime config"
```

### Task 2: Introduce message-oriented workflow state

**Files:**
- Modify: `src/base_agent_system/workflow/state.py`
- Modify: `src/base_agent_system/api/models.py`
- Test: `tests/contract/test_chat_ui_api.py`

**Step 1: Write the failing test**

Extend `tests/contract/test_chat_ui_api.py` so `/api/chat` sends a full message array through to the workflow service instead of only a final query string. The stub should assert it receives all relevant conversation messages and thread ID.

Example expectation shape:

```python
assert messages == [
    {"role": "user", "content": "First question"},
    {"role": "assistant", "content": "First answer"},
    {"role": "user", "content": "Follow-up"},
]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_chat_ui_api.py -q`

Expected: FAIL because the backend currently only extracts the latest user text.

**Step 3: Write minimal implementation**

- Expand the workflow state from `query`-centric to message-centric
- Add a backend message representation that is simple and explicit
- Keep `thread_id`, `citations`, and `debug`
- Preserve compatibility for `/query` separately rather than overloading chat state everywhere

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_chat_ui_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/state.py src/base_agent_system/api/models.py tests/contract/test_chat_ui_api.py
git commit -m "refactor: move chat workflow to message state"
```

### Task 3: Wrap retrieval and Graphiti memory as LangChain tools

**Files:**
- Create: `src/base_agent_system/workflow/agent_tools.py`
- Modify: `src/base_agent_system/runtime_services.py`
- Test: `tests/contract/test_react_agent_tools.py`

**Step 1: Write the failing test**

Create `tests/contract/test_react_agent_tools.py` covering two tools:

```python
def test_search_docs_tool_formats_grounding_payload():
    ...

def test_search_memory_tool_uses_thread_id_and_formats_memory_payload():
    ...
```

The tests should verify:
- docs tool calls the retrieval service with the provided query
- memory tool calls Graphiti memory lookup with `thread_id`
- both tools return concise text useful for an LLM
- citations/debug metadata can be captured for final response assembly

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_react_agent_tools.py -q`

Expected: FAIL because the tool module does not exist yet.

**Step 3: Write minimal implementation**

- Create a small tool module exposing:
  - `search_docs`
  - `search_memory`
- Use LangChain `@tool`
- Keep returned payloads simple, deterministic, and grounded
- Avoid converting the entire retrieval/memory layer to LangChain-native stores

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_react_agent_tools.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/agent_tools.py src/base_agent_system/runtime_services.py tests/contract/test_react_agent_tools.py
git commit -m "feat: add retrieval and memory agent tools"
```

### Task 4: Build the backend LangGraph ReAct agent

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Modify: `src/base_agent_system/runtime_services.py`
- Create: `tests/contract/test_react_agent_workflow.py`

**Step 1: Write the failing test**

Create a focused contract test proving the workflow builder now constructs a ReAct-style agent that can use tools dynamically.

The test should stub the model and assert:
- the model can decide to call `search_docs`
- tool results are fed back into the agent loop
- the final result is a natural-language assistant answer
- the final result carries citations/debug metadata

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_react_agent_workflow.py -q`

Expected: FAIL because the current workflow is still a fixed node graph.

**Step 3: Write minimal implementation**

- Build a prebuilt ReAct agent using the current LangGraph-compatible helper for the repo’s installed version
- Use `MessagesState` or the nearest equivalent message-state primitive
- Instantiate the model via `langchain-openai` against AI Gateway base URL
- Preserve checkpointer integration from the existing `WorkflowService`
- Keep a thin adapter layer that returns the same backend response envelope: `thread_id`, `answer`, `citations`, `debug`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_react_agent_workflow.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/graph.py src/base_agent_system/runtime_services.py tests/contract/test_react_agent_workflow.py
git commit -m "feat: replace synthetic workflow with react agent"
```

### Task 5: Persist real conversation turns after agent completion

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Modify: `src/base_agent_system/workflow/nodes.py`
- Test: `tests/integration/test_graphiti_memory.py`

**Step 1: Write the failing test**

Add or extend an integration test so a user turn and a real assistant answer are persisted after the agent finishes.

The test should verify:
- user message is stored
- assistant message is stored
- same thread can later retrieve prior assistant context from Graphiti

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_graphiti_memory.py -q`

Expected: FAIL for the new persistence expectation.

**Step 3: Write minimal implementation**

- Remove synthetic-answer-specific persistence coupling from the old node path if necessary
- Persist conversation turns after the agent produces its final assistant output
- Keep memory storage responsibility in one clear place

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_graphiti_memory.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py src/base_agent_system/workflow/nodes.py tests/integration/test_graphiti_memory.py
git commit -m "feat: persist react agent conversation turns"
```

### Task 6: Add backend streaming chat transport

**Files:**
- Modify: `src/base_agent_system/api/routes_chat.py`
- Modify: `src/base_agent_system/runtime_services.py`
- Create: `tests/contract/test_chat_ui_streaming.py`

**Step 1: Write the failing test**

Create `tests/contract/test_chat_ui_streaming.py` that verifies `/api/chat` can return a streaming response for the AI SDK chat protocol.

Cover:
- HTTP 200
- streaming content type
- streamed assistant text appears in the response body
- thread metadata and citations/debug are still available in the final stream or response annotations

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_chat_ui_streaming.py -q`

Expected: FAIL because `/api/chat` currently returns a plain JSON payload.

**Step 3: Write minimal implementation**

- Add a streaming path in FastAPI for `/api/chat`
- The runtime service should expose a streaming iterator/generator over agent output
- Keep the final backend payload compatible with the UI side panel metadata requirements
- Do not remove the ability to test non-streaming behavior if the existing contract still needs it; split endpoints or behavior only if necessary and justified

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_chat_ui_streaming.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_chat.py src/base_agent_system/runtime_services.py tests/contract/test_chat_ui_streaming.py
git commit -m "feat: stream chat responses from backend agent"
```

### Task 7: Migrate the web chat UI to AI SDK `useChat`

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/package.json` if needed
- Test: `tests/smoke/test_web_chat_app_layout.py`

**Step 1: Write the failing test**

Update `tests/smoke/test_web_chat_app_layout.py` to assert the page uses the AI SDK chat hook and still points at `/api/chat`.

Examples:

```python
assert "useChat" in page_text
assert "/api/chat" in page_text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_web_chat_app_layout.py -q`

Expected: FAIL because the page currently uses manual `fetch`.

**Step 3: Write minimal implementation**

- Replace manual request state with `useChat`
- Keep the current UI visual structure where practical
- Stream assistant text live
- Preserve thread ID handling
- Preserve citations/debug side panel by reading final assistant metadata or streamed data parts

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_web_chat_app_layout.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add web/app/page.tsx web/package.json tests/smoke/test_web_chat_app_layout.py
git commit -m "feat: migrate chat ui to ai sdk usechat"
```

### Task 8: Keep `/query` and app contracts coherent

**Files:**
- Modify: `src/base_agent_system/api/routes_query.py`
- Modify: `src/base_agent_system/api/models.py`
- Test: `tests/contract/test_query_api.py`

**Step 1: Write the failing test**

Add or update a query API contract test that proves `/query` still returns a useful backend answer after the agent migration.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_query_api.py -q`

Expected: FAIL if the migration breaks the legacy path.

**Step 3: Write minimal implementation**

- Keep `/query` functional by routing it through the same backend agent or a thin compatibility adapter
- Do not maintain two different answer-generation systems if one adapter can serve both

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_query_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_query.py src/base_agent_system/api/models.py tests/contract/test_query_api.py
git commit -m "refactor: keep query api aligned with chat agent"
```

### Task 9: Update deployment and docs for AI Gateway-backed chat

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Modify: `infra/helm/base-agent-system/templates/configmap.yaml`
- Modify: `infra/helm/base-agent-system/templates/secret.yaml`
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.example.yaml`
- Test: `tests/smoke/test_kubernetes_runbooks.py`

**Step 1: Write the failing test**

Extend runbook/config smoke tests to assert the repo documents AI Gateway-backed backend chat and the necessary env configuration.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: FAIL because the docs and chart env vars do not mention the new backend model path yet.

**Step 3: Write minimal implementation**

- Document required env vars for AI Gateway
- Document that LLM invocation happens in the backend
- Add chart config/secret entries only for what is actually required
- Keep local-only secrets in `values.local.yaml`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md docs/runbooks/kubernetes-deployment.md infra/helm/base-agent-system/templates/configmap.yaml infra/helm/base-agent-system/templates/secret.yaml infra/helm/base-agent-system/values.yaml infra/helm/environments/kind/values.local.example.yaml tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: add backend ai gateway chat configuration"
```

### Task 10: Full verification in local kind

**Files:**
- Verify only; no required file modifications

**Step 1: Build the frontend and backend**

Run:

```bash
npm --prefix web run build
python3 -m pytest tests -q
docker build -t base-agent-system:0.1.0 .
kind load docker-image base-agent-system:0.1.0 --name base-agent-system
```

Expected:
- Next export succeeds
- test suite passes
- image builds
- kind image load succeeds

**Step 2: Deploy the updated chart**

Run the repo’s supported deployment command for kind. If `helmfile` is unavailable in the shell, use the equivalent Helm release update command already used in this repository session.

Expected: release updates cleanly and app pods become ready.

**Step 3: Verify live chat behavior**

Run:

```bash
curl -i http://127.0.0.1:8000/chat
curl -i http://127.0.0.1:8000/chat/_next/static/...   # use a real asset path from the page
curl -i http://127.0.0.1:8000/live
curl -i http://127.0.0.1:8000/ready
```

Expected:
- `/chat` returns the packaged UI
- `_next` asset returns `200`
- health endpoints return `200`

**Step 4: Verify real assistant behavior manually**

Use the browser UI and confirm:
- assistant messages stream in progressively
- the agent can answer simple chat without tools
- the agent can answer retrieval-heavy questions using docs
- follow-up questions can use thread memory
- citations/debug update when tool usage occurs

**Step 5: Final verification command**

Run: `python3 -m pytest tests -q`

Expected: full suite passes with fresh output.

**Step 6: Commit**

```bash
git status --short
git add .
git commit -m "feat: add streaming react chat agent"
```
