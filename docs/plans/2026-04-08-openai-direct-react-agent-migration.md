# OpenAI Direct ReAct Agent Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the Vercel AI Gateway dependency from the backend LangGraph ReAct agent and switch the system to direct OpenAI access using `OPENAI_API_KEY`, while preserving the existing FastAPI, LangGraph, Graphiti, Postgres, and web chat architecture.

**Architecture:** Keep the current backend-owned LangGraph ReAct agent and its document retrieval and memory tools. Replace only the provider-specific wiring in the model construction path so `ChatOpenAI` talks directly to OpenAI instead of going through AI Gateway. Remove AI Gateway-specific runtime config, Helm config, docs, and tests, then re-verify both the test suite and the kind deployment.

**Tech Stack:** FastAPI, LangGraph, LangChain, LangChain OpenAI, OpenAI API, Graphiti, Postgres, pytest, Helm, kind, Next.js.

---

### Task 1: Replace AI Gateway runtime settings with direct OpenAI settings

**Files:**
- Modify: `src/base_agent_system/config.py`
- Test: `tests/integration/test_config.py`

**Step 1: Write the failing test**

Update `tests/integration/test_config.py` so the config contract no longer expects AI Gateway-specific settings and instead expects the backend to rely on `OPENAI_API_KEY` plus `BASE_AGENT_SYSTEM_LLM_MODEL`.

Example expectations:

```python
settings = load_settings()
assert settings.llm_model == "gpt-4o-mini"
assert settings.openai_api_key_name == "OPENAI_API_KEY"
assert not hasattr(settings, "ai_gateway_api_key_name")
assert not hasattr(settings, "ai_gateway_base_url")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_config.py -q`

Expected: FAIL because `Settings` still exposes AI Gateway fields.

**Step 3: Write minimal implementation**

- Remove `ai_gateway_api_key_name` from `Settings`
- Remove `ai_gateway_base_url` from `Settings`
- Remove their `load_settings()` environment loading
- Keep `llm_model`
- Keep `openai_api_key_name`
- Do not add new provider abstractions or speculative provider enums

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_config.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/config.py tests/integration/test_config.py
git commit -m "refactor: remove ai gateway runtime settings"
```

### Task 2: Switch LangGraph model construction to direct OpenAI

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Test: `tests/contract/test_react_agent_workflow.py`

**Step 1: Write the failing test**

Update `tests/contract/test_react_agent_workflow.py` so it asserts the ReAct workflow builds `ChatOpenAI` without a custom `base_url`, and uses the OpenAI key path directly.

Example expectation:

```python
assert observed == {
    "model": "gpt-4o-mini",
    "api_key": "test-openai-key",
}
assert "base_url" not in observed
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/test_react_agent_workflow.py -q`

Expected: FAIL because `_build_model()` still passes the AI Gateway base URL and gateway key resolution.

**Step 3: Write minimal implementation**

- Replace `_resolve_gateway_api_key(...)` with direct OpenAI key resolution
- Update `_build_model(settings)` to construct:

```python
ChatOpenAI(
    model=settings.llm_model,
    api_key=<resolved openai key>,
)
```

- Remove AI Gateway-specific helper logic from `graph.py`
- Keep the synthetic workflow fallback logic minimal and test-friendly

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/test_react_agent_workflow.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/graph.py tests/contract/test_react_agent_workflow.py
git commit -m "refactor: use openai directly for react agent"
```

### Task 3: Remove AI Gateway-specific environment requirements from tests

**Files:**
- Modify: `tests/contract/test_chat_ui_api.py`
- Modify: `tests/contract/test_chat_ui_streaming.py`
- Modify: `tests/contract/test_query_api.py`
- Modify: `tests/contract/test_ingest_api.py`
- Modify: `tests/contract/test_chat_ui_assets.py`
- Modify: `tests/integration/test_workflow.py`
- Modify: `tests/integration/test_graphiti_memory.py`
- Modify: `tests/integration/test_config.py`
- Modify: `tests/integration/test_end_to_end_query_flow.py`
- Modify: `tests/integration/test_api_contributors.py`

**Step 1: Write the failing test**

Pick one representative contract test and one representative integration test, remove their `AI_GATEWAY_API_KEY` seeding, and assert the app still boots and the real workflow path can be selected with `OPENAI_API_KEY`.

Example expectation:

```python
monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
response = client.post(...)
assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/contract/test_query_api.py tests/integration/test_workflow.py -q
```

Expected: FAIL because some tests still rely on `AI_GATEWAY_API_KEY` setup.

**Step 3: Write minimal implementation**

- Replace `AI_GATEWAY_API_KEY` test env setup with `OPENAI_API_KEY` in all affected tests
- Preserve `app_env="test"` usage where tests intentionally need synthetic fallback behavior
- Do not broaden provider logic just to satisfy tests; align tests to the simplified runtime contract

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/contract/test_query_api.py tests/integration/test_workflow.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/contract/test_query_api.py tests/contract/test_ingest_api.py tests/contract/test_chat_ui_assets.py tests/integration/test_workflow.py tests/integration/test_graphiti_memory.py tests/integration/test_config.py tests/integration/test_end_to_end_query_flow.py tests/integration/test_api_contributors.py
git commit -m "test: remove ai gateway env usage"
```

### Task 4: Remove AI Gateway from Helm runtime configuration

**Files:**
- Modify: `infra/helm/base-agent-system/templates/configmap.yaml`
- Modify: `infra/helm/base-agent-system/templates/secret.yaml`
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.example.yaml`
- Test: `tests/smoke/test_container_contract.py`

**Step 1: Write the failing test**

Update `tests/smoke/test_container_contract.py` so it no longer expects `BASE_AGENT_SYSTEM_AI_GATEWAY_API_KEY_NAME` or `BASE_AGENT_SYSTEM_AI_GATEWAY_BASE_URL`, and instead asserts the Helm runtime contract only requires `OPENAI_API_KEY` for the backend LLM path.

Example expectation:

```python
assert "BASE_AGENT_SYSTEM_AI_GATEWAY_API_KEY_NAME" not in config_text
assert "BASE_AGENT_SYSTEM_AI_GATEWAY_BASE_URL" not in config_text
assert "OPENAI_API_KEY" in secret_text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_container_contract.py -q`

Expected: FAIL because Helm templates still include AI Gateway config.

**Step 3: Write minimal implementation**

- Remove AI Gateway env entries from the config map template
- Remove `AI_GATEWAY_API_KEY` from the secret template
- Remove AI Gateway defaults from chart values
- Update kind local example values to require `openaiApiKey` and not `aiGatewayApiKey`
- Do not change unrelated secret/config keys

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_container_contract.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add infra/helm/base-agent-system/templates/configmap.yaml infra/helm/base-agent-system/templates/secret.yaml infra/helm/base-agent-system/values.yaml infra/helm/environments/kind/values.local.example.yaml tests/smoke/test_container_contract.py
git commit -m "refactor: remove ai gateway helm config"
```

### Task 5: Update docs and runbooks to describe direct OpenAI usage

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Modify: `tests/smoke/test_kubernetes_runbooks.py`

**Step 1: Write the failing test**

Update `tests/smoke/test_kubernetes_runbooks.py` so it no longer expects `AI_GATEWAY_API_KEY` instructions and instead expects `OPENAI_API_KEY` guidance.

Example expectation:

```python
assert "OPENAI_API_KEY" in text
assert "AI_GATEWAY_API_KEY" not in text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: FAIL because docs still mention Vercel AI Gateway.

**Step 3: Write minimal implementation**

- Update README language from "uses Vercel AI Gateway" to "uses OpenAI directly"
- Update local development env instructions to remove AI Gateway variables
- Update Kubernetes deployment docs to require `OPENAI_API_KEY` only
- Leave a brief note that LiteLLM proxy could be added later if needed, but do not document it as current behavior

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md docs/runbooks/kubernetes-deployment.md tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: switch llm setup guidance to openai direct"
```

### Task 6: Run full verification and redeploy to kind

**Files:**
- Verify only: working tree changes from Tasks 1-5

**Step 1: Run targeted verification**

Run:

```bash
python3 -m pytest tests/contract/test_react_agent_workflow.py tests/contract/test_query_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
python3 -m pytest tests/integration/test_config.py tests/integration/test_workflow.py tests/integration/test_end_to_end_query_flow.py -q
python3 -m pytest tests/smoke/test_container_contract.py tests/smoke/test_kubernetes_runbooks.py -q
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
rtk curl -i -H "Content-Type: application/json" --data-binary '{"thread_id":"smoke-query","query":"What does the seed document explain?"}' http://127.0.0.1:8000/query
rtk curl -i -H "Accept: text/plain" -H "Content-Type: application/json" --data-binary '{"threadId":"smoke-chat","messages":[{"role":"user","content":"What does the seed document explain?"}]}' http://127.0.0.1:8000/api/chat
```

Expected:
- `/live` -> `200`
- `/ready` -> `200`
- `/chat` -> `200`
- `/query` -> `200` with grounded answer
- `/api/chat` -> `200` with text/plain streaming response

**Step 5: Commit**

```bash
git add .
git commit -m "refactor: switch backend react agent to direct openai"
```
