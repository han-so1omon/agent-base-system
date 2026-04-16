# Firecrawl Cloud + Opik Cloud Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Switch the app to Firecrawl Cloud and add real Opik Cloud tracing for API, workflow, and worker branch execution.

**Architecture:** Reuse the existing Firecrawl client path by moving its URL and key to app-level cloud config and disabling self-hosted cluster deployment. Add a thin observability adapter around the current workflow and worker seams so Opik is optional, isolated from most runtime code, and keyed around one canonical trace unit: a single interaction branch execution.

**Tech Stack:** FastAPI, LangGraph, LangChain, Firecrawl Cloud API, Opik Python SDK, Helm, Kubernetes, pytest

---

### Task 1: Add Firecrawl Cloud app config and stop relying on self-hosted URL injection

**Files:**
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/base-agent-system/templates/configmap.yaml`
- Modify: `infra/helm/base-agent-system/templates/secret.yaml`
- Modify: `infra/helm/environments/kind/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.yaml`
- Test: `tests/smoke/test_base_agent_system_helm_chart.py`
- Test: `tests/integration/test_config.py`

**Step 1: Write the failing test**

Add a Helm/config contract test that expects app-level Firecrawl env vars to come from values instead of being hardcoded to `http://firecrawl-api:3002`.

Add a config test for a cloud URL like:

```python
def test_config_loads_firecrawl_cloud_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", "https://api.firecrawl.dev")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY", "fc-key")

    settings = load_settings()

    assert settings.firecrawl_api_url == "https://api.firecrawl.dev"
    assert settings.firecrawl_api_key == "fc-key"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_config.py tests/smoke/test_base_agent_system_helm_chart.py -q`

Expected: failing assertions because the chart still hardcodes the in-cluster Firecrawl URL.

**Step 3: Write minimal implementation**

Add to chart values:
- `config.firecrawlApiUrl`
- `secret.firecrawlApiKey`

Render into env:
- `BASE_AGENT_SYSTEM_FIRECRAWL_API_URL`
- `BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY`

Remove the hardcoded conditional URL from `infra/helm/base-agent-system/templates/configmap.yaml`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_config.py tests/smoke/test_base_agent_system_helm_chart.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add infra/helm/base-agent-system/values.yaml infra/helm/base-agent-system/templates/configmap.yaml infra/helm/base-agent-system/templates/secret.yaml infra/helm/environments/kind/values.yaml infra/helm/environments/kind/values.local.yaml tests/integration/test_config.py tests/smoke/test_base_agent_system_helm_chart.py
git commit -m "feat: configure app for firecrawl cloud"
```

### Task 2: Disable self-hosted Firecrawl in kind

**Files:**
- Modify: `infra/helm/environments/kind/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.yaml`
- Test: `tests/smoke/test_base_agent_system_helm_chart.py`

**Step 1: Write the failing test**

Add or extend a chart smoke test so `kind` values expect `firecrawl.enabled` to be false when cloud mode is configured.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/smoke/test_base_agent_system_helm_chart.py -q`

Expected: FAIL because `kind` still enables self-hosted Firecrawl.

**Step 3: Write minimal implementation**

Set `firecrawl.enabled: false` for `kind`.

Keep `infra/helm/base-agent-system/templates/firecrawl.yaml` gated, but not active in this environment.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/smoke/test_base_agent_system_helm_chart.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add infra/helm/environments/kind/values.yaml infra/helm/environments/kind/values.local.yaml tests/smoke/test_base_agent_system_helm_chart.py
git commit -m "chore: disable self-hosted firecrawl in kind"
```

### Task 3: Add optional Opik runtime settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/base_agent_system/config.py`
- Modify: `tests/integration/test_config.py`
- Create: `tests/integration/test_opik_config.py`

**Step 1: Write the failing test**

Create config tests covering:
- Opik disabled by default
- env loading for:
  - `BASE_AGENT_SYSTEM_OPIK_ENABLED`
  - `BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME`
  - `BASE_AGENT_SYSTEM_OPIK_WORKSPACE`
  - `BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME`
  - `BASE_AGENT_SYSTEM_OPIK_URL`
  - `BASE_AGENT_SYSTEM_OPIK_USE_LOCAL`

Example:

```python
def test_config_loads_opik_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_ENABLED", "true")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME", "base-agent-system")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_WORKSPACE", "default")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME", "OPIK_API_KEY")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_URL", "https://www.comet.com/opik/api")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_USE_LOCAL", "false")

    settings = load_settings()

    assert settings.opik_enabled is True
    assert settings.opik_project_name == "base-agent-system"
    assert settings.opik_workspace == "default"
    assert settings.opik_api_key_name == "OPIK_API_KEY"
    assert settings.opik_url == "https://www.comet.com/opik/api"
    assert settings.opik_use_local is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_config.py tests/integration/test_opik_config.py -q`

Expected: FAIL because Opik settings do not exist yet.

**Step 3: Write minimal implementation**

Add `opik` dependency to `pyproject.toml`.

Add to `Settings`:
- `opik_enabled: bool = False`
- `opik_project_name: str = "base-agent-system"`
- `opik_workspace: str = ""`
- `opik_api_key_name: str = "OPIK_API_KEY"`
- `opik_url: str = ""`
- `opik_use_local: bool = False`

Extend `load_settings()` accordingly.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_config.py tests/integration/test_opik_config.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml src/base_agent_system/config.py tests/integration/test_config.py tests/integration/test_opik_config.py
git commit -m "feat: add optional opik runtime settings"
```

### Task 4: Add Helm wiring for Opik Cloud config

**Files:**
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/base-agent-system/templates/configmap.yaml`
- Modify: `infra/helm/base-agent-system/templates/secret.yaml`
- Modify: `infra/helm/environments/kind/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.yaml`
- Test: `tests/smoke/test_container_contract.py`

**Step 1: Write the failing test**

Add a container env contract test that expects:
- `BASE_AGENT_SYSTEM_OPIK_ENABLED`
- `BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME`
- `BASE_AGENT_SYSTEM_OPIK_WORKSPACE`
- `BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME`
- `BASE_AGENT_SYSTEM_OPIK_URL`
- `BASE_AGENT_SYSTEM_OPIK_USE_LOCAL`
- `OPIK_API_KEY`

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/smoke/test_container_contract.py -q`

Expected: FAIL because the chart does not expose Opik env vars yet.

**Step 3: Write minimal implementation**

Add values for Opik config and secret.

Render config env vars in `infra/helm/base-agent-system/templates/configmap.yaml`.

Render `OPIK_API_KEY` in `infra/helm/base-agent-system/templates/secret.yaml`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/smoke/test_container_contract.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add infra/helm/base-agent-system/values.yaml infra/helm/base-agent-system/templates/configmap.yaml infra/helm/base-agent-system/templates/secret.yaml infra/helm/environments/kind/values.yaml infra/helm/environments/kind/values.local.yaml tests/smoke/test_container_contract.py
git commit -m "feat: wire app chart to opik cloud"
```

### Task 5: Create the Opik observability adapter

**Files:**
- Create: `src/base_agent_system/observability/__init__.py`
- Create: `src/base_agent_system/observability/opik.py`
- Modify: `src/base_agent_system/dependencies.py`
- Test: `tests/integration/test_opik_tracing.py`

**Step 1: Write the failing test**

Create adapter tests covering:
- noop behavior when Opik is disabled
- adapter bootstrap when Opik is enabled
- start and end branch trace
- nested span support
- metadata tagging by:
  - `thread_id`
  - `interaction_id`
  - `parent_interaction_id`

Example skeleton:

```python
def test_noop_observability_service_returns_safe_context() -> None:
    service = NoopObservabilityService()
    with service.start_branch_trace(thread_id="t1", interaction_id="i1") as trace:
        assert trace is not None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_opik_tracing.py -q`

Expected: FAIL because the observability module does not exist yet.

**Step 3: Write minimal implementation**

Create:
- `NoopObservabilityService`
- `OpikObservabilityService`

Methods:
- `start_branch_trace(...)`
- `start_span(...)`
- `mark_success(...)`
- `mark_error(...)`
- `flush()`

Create the service centrally in `src/base_agent_system/dependencies.py` and attach it to app/runtime state.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_opik_tracing.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/observability src/base_agent_system/dependencies.py tests/integration/test_opik_tracing.py
git commit -m "feat: add opik observability adapter"
```

### Task 6: Instrument canonical workflow branch execution

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Test: `tests/integration/test_async_workflow_service.py`
- Test: `tests/integration/test_opik_tracing.py`

**Step 1: Write the failing test**

Add tests verifying `WorkflowService.arun(...)`:
- creates one branch trace
- attaches:
  - `thread_id`
  - `interaction_id`
  - `parent_interaction_id`
  - branch kind: root vs child
  - tool counts
  - tools used
  - citation count
  - final status
- records failures as failed traces

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py -q`

Expected: FAIL because workflow execution is not traced yet.

**Step 3: Write minimal implementation**

Add the observability service to workflow service construction.

Wrap the full `WorkflowService.arun(...)` branch execution.

Record summary metadata only.

Do not refactor unrelated workflow logic.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py
git commit -m "feat: trace workflow branches with opik"
```

### Task 7: Add API request correlation

**Files:**
- Modify: `src/base_agent_system/api/routes_interact.py`
- Modify: `src/base_agent_system/api/routes_chat.py`
- Test: `tests/contract/test_interact_api.py`
- Test: `tests/contract/test_chat_ui_api.py`
- Test: `tests/contract/test_chat_ui_streaming.py`

**Step 1: Write the failing test**

Add request correlation tests for:
- `/interact`
- `/api/chat`
- streaming and non-streaming requests

Verify request metadata is passed into the branch trace path.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q`

Expected: FAIL because request metadata is not yet attached to traces.

**Step 3: Write minimal implementation**

Thread lightweight request metadata into workflow execution.

Avoid broad API refactors.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_interact.py src/base_agent_system/api/routes_chat.py tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py
git commit -m "feat: add api request correlation for opik"
```

### Task 8: Add worker and child-branch correlation

**Files:**
- Modify: `src/base_agent_system/workers/tasks.py`
- Test: `tests/integration/test_arq_worker.py`
- Create: `tests/integration/test_opik_worker_tracing.py`

**Step 1: Write the failing test**

Create worker tracing tests verifying:
- worker-run branch traces are created
- child branch traces link to parent interaction ids
- failures in worker tasks are marked correctly

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py -q`

Expected: FAIL because worker tracing does not exist yet.

**Step 3: Write minimal implementation**

Start and propagate trace context in `run_interaction_branch(...)`.

Attach parent and child metadata.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/base_agent_system/workers/tasks.py tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py
git commit -m "feat: trace worker child branches with opik"
```

### Task 9: Verify Firecrawl Cloud path at runtime

**Files:**
- Modify if needed: `tests/contract/test_firecrawl_client.py`
- Modify if needed: `tests/contract/test_firecrawl_tools.py`
- Modify if needed: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

Add or update tests to verify:
- Firecrawl tools still register when cloud URL is configured
- bearer auth header still matches expected client behavior
- no dependency on self-hosted cluster URL remains in app config

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py tests/integration/test_workflow.py -q`

Expected: FAIL only if current assumptions are incompatible with cloud config.

**Step 3: Write minimal implementation**

Only patch runtime code if tests reveal a cloud-specific gap.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py tests/integration/test_workflow.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/contract/test_firecrawl_client.py tests/contract/test_firecrawl_tools.py tests/integration/test_workflow.py src/base_agent_system/research/firecrawl_client.py src/base_agent_system/workflow/graph.py
git commit -m "fix: verify firecrawl cloud client path"
```

### Task 10: Real deployment verification

**Files:**
- No new code unless verification reveals a bug

**Step 1: Deploy**

Run: `bash ./scripts/deploy-kind.sh`

Expected: app deploys successfully with self-hosted Firecrawl disabled.

**Step 2: Verify app env**

Run: `kubectl exec -n base-agent-system deploy/base-agent-system -- env | grep -E 'FIRECRAWL|OPIK'`

Expected: cloud Firecrawl and Opik env vars are present.

**Step 3: Verify Firecrawl Cloud path**

Execute one real app request that triggers a Firecrawl-backed tool path.

Expected: response succeeds using Firecrawl Cloud credentials.

**Step 4: Verify Opik Cloud path**

Execute:
- one root interaction
- one child branch interaction

Confirm traces appear in the configured Opik project and workspace.

**Step 5: Commit if no further fixes are needed**

```bash
git add <all changed files>
git commit -m "feat: switch to cloud firecrawl and opik tracing"
```

### Task 11: Documentation cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Optional Test: `tests/smoke/test_bootstrap_docs.py`
- Optional Test: `tests/smoke/test_kubernetes_runbooks.py`

**Step 1: Write the failing docs assertion**

Document:
- Firecrawl Cloud config
- Opik Cloud config
- required secrets
- how to verify traces and cloud requests
- that `kind` no longer runs self-hosted Firecrawl by default

If docs smoke tests exist for these paths, extend them first.

**Step 2: Update docs**

Keep docs focused on setup and verification.

**Step 3: Run applicable docs smoke tests**

Run: `python -m pytest tests/smoke/test_bootstrap_docs.py tests/smoke/test_kubernetes_runbooks.py -q`

Expected: PASS if the docs assertions exist.

**Step 4: Commit**

```bash
git add README.md docs/runbooks/local-development.md tests/smoke/test_bootstrap_docs.py tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: add cloud firecrawl and opik setup"
```

## Open Questions To Resolve Before Execution

- Exact Firecrawl Cloud base URL
- Exact Opik Cloud base URL
- Exact Opik project name
- Exact Opik workspace name
- Whether `kind` tracked values should include the non-secret cloud URLs by default

## Execution Evidence Required

- unit and integration tests for config and tracing
- Helm and chart contract tests
- real deployed env inspection
- real Firecrawl-backed request through the app
- real Opik trace visible in cloud

## Residual Risks

- Opik SDK API shape may differ from the assumptions in the earlier planning doc, so adapter tests must be written before locking implementation.
- API request correlation may need a small request-context carrier to avoid invasive route changes.
- Cloud trace flush behavior may need tuning to avoid slowing requests.
