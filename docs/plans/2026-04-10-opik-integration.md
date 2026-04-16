# Opik Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Opik to the base-agent system for branch-centric tracing, evaluations, and experiment tracking, with flexible and extensible metrics that can evolve as we learn from real runs.

**Architecture:** Keep LangGraph and LangChain as the runtime. Add Opik as an observability and evaluation layer around existing request, workflow, and worker seams. Use interaction branch execution as the canonical trace unit, with `thread_id` and request metadata attached for aggregation.

**Tech Stack:** FastAPI, LangGraph, LangChain, OpenAI-compatible models, ARQ-style workers, Postgres-backed interaction tree, Opik Python SDK

---

## Scope

Phase 1 should deliver:
- optional Opik configuration
- branch-level tracing around `WorkflowService.arun(...)`
- API request correlation
- worker and child-branch correlation
- basic structured metadata capture
- a pluggable evaluation abstraction with a minimal starter metric set
- at least one way to run evals and experiments offline from curated inputs

Phase 1 should not deliver:
- DSPy integration
- full human feedback workflows
- broad instrumentation of every helper function
- a redesign of the LangGraph runtime

## Canonical Model

- Canonical trace unit: one interaction branch execution
- Grouping dimensions:
  - request
  - thread
  - parent and child branch tree
- Evaluation unit: one interaction branch result
- Metric design principle:
  - runtime records primitive signals
  - evaluation layer computes derived metrics
  - metrics are pluggable and versioned

## Planned Files

**Modify**
- `pyproject.toml`
- `src/base_agent_system/config.py`
- `src/base_agent_system/dependencies.py`
- `src/base_agent_system/runtime_services.py`
- `src/base_agent_system/workers/tasks.py`
- `src/base_agent_system/api/routes_interact.py`
- `src/base_agent_system/api/routes_chat.py`
- `README.md`
- `docs/runbooks/local-development.md`

**Create**
- `src/base_agent_system/observability/__init__.py`
- `src/base_agent_system/observability/opik.py`
- `src/base_agent_system/evaluations/__init__.py`
- `src/base_agent_system/evaluations/models.py`
- `src/base_agent_system/evaluations/metrics.py`
- `src/base_agent_system/evaluations/registry.py`
- `src/base_agent_system/evaluations/opik_runner.py`
- `tests/integration/test_opik_tracing.py`
- `tests/integration/test_opik_worker_tracing.py`
- `tests/integration/test_opik_config.py`
- `tests/contract/test_evaluation_metrics.py`

Optional if needed during implementation:
- `src/base_agent_system/evaluations/datasets.py`
- `tests/integration/test_opik_eval_runner.py`

### Task 1: Add Optional Opik Configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/base_agent_system/config.py`
- Test: `tests/integration/test_config.py`
- Create: `tests/integration/test_opik_config.py`

**Step 1: Write the failing config tests**

Add tests covering:
- Opik disabled by default
- Opik env vars load correctly
- local and self-hosted mode fields are optional but typed
- project name defaults sanely

Expected settings to add:
- `opik_enabled: bool = False`
- `opik_project_name: str = "base-agent-system"`
- `opik_workspace: str = ""`
- `opik_api_key_name: str = "OPIK_API_KEY"`
- `opik_url: str = ""`
- `opik_use_local: bool = False`

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/integration/test_config.py tests/integration/test_opik_config.py -q
```

Expected:
- failing assertions for missing config fields

**Step 3: Add minimal implementation**

- add `opik` dependency to `pyproject.toml`
- extend `Settings`
- extend `load_settings()`
- do not require Opik config when disabled

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/integration/test_config.py tests/integration/test_opik_config.py -q
```

**Step 5: Commit**

```bash
git add pyproject.toml src/base_agent_system/config.py tests/integration/test_config.py tests/integration/test_opik_config.py
git commit -m "feat: add optional opik runtime settings"
```

### Task 2: Add an Opik Client and Tracing Adapter Layer

**Files:**
- Create: `src/base_agent_system/observability/__init__.py`
- Create: `src/base_agent_system/observability/opik.py`
- Modify: `src/base_agent_system/dependencies.py`
- Test: `tests/integration/test_opik_tracing.py`

**Step 1: Write the failing tracing-adapter tests**

Cover:
- no-op behavior when Opik is disabled
- tracer and client bootstrap when enabled
- ability to start and end a branch trace with metadata
- ability to nest spans
- ability to tag and group by `thread_id`, `interaction_id`, `parent_interaction_id`

Design target:
- one thin abstraction so runtime code does not import Opik everywhere
- something like:
  - `ObservabilityService`
  - `NoopObservabilityService`
  - `OpikObservabilityService`

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/integration/test_opik_tracing.py -q
```

**Step 3: Implement the adapter**

In `observability/opik.py`:
- initialize and configure Opik when enabled
- expose helper methods like:
  - `start_branch_trace(...)`
  - `start_span(...)`
  - `record_feedback(...)` later-compatible
  - `flush()` or a no-op equivalent
- keep the interface small and runtime-safe

In `dependencies.py`:
- create and attach the observability service to app state or runtime state

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/integration/test_opik_tracing.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/observability src/base_agent_system/dependencies.py tests/integration/test_opik_tracing.py
git commit -m "feat: add opik observability adapter"
```

### Task 3: Instrument Canonical Branch Execution

**Files:**
- Modify: `src/base_agent_system/runtime_services.py`
- Test: `tests/integration/test_async_workflow_service.py`
- Test: `tests/integration/test_opik_tracing.py`

**Step 1: Write the failing workflow tracing tests**

Add tests for `WorkflowService.arun(...)` that verify:
- one branch trace is created per run
- trace metadata includes:
  - `thread_id`
  - `interaction_id`
  - `parent_interaction_id`
  - request kind: root vs child
  - tool stats from `result["interaction"]`
  - citation count
  - artifact count
  - final status
- failures are recorded as failed traces
- disabled Opik does not change behavior

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py -q
```

**Step 3: Implement minimal tracing in `WorkflowService.arun(...)`**

Wrap the full branch execution in the observability service.
Use this method as the canonical trace boundary because it already has:
- inputs
- normalized messages
- ids
- outputs
- persistence side effects

Record:
- input summary, not raw uncontrolled dumps if avoidable
- output summary
- latency
- debug counters
- branch status

Do not deeply refactor the workflow service yet.

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/runtime_services.py tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py
git commit -m "feat: trace workflow branches with opik"
```

### Task 4: Add API Request Correlation

**Files:**
- Modify: `src/base_agent_system/api/routes_interact.py`
- Modify: `src/base_agent_system/api/routes_chat.py`
- Test: `tests/contract/test_interact_api.py`
- Test: `tests/contract/test_chat_ui_api.py`
- Test: `tests/contract/test_chat_ui_streaming.py`

**Step 1: Write the failing API tracing tests**

Cover:
- request-level metadata is attached to the branch trace
- request source is distinguishable:
  - `/interact`
  - `/api/chat`
  - streamed chat response
- no response shape regressions

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

**Step 3: Implement request correlation**

Pass request-level metadata into workflow execution or observability context:
- route name
- message count
- streaming flag
- thread id
- request id if generated

Keep the API contract unchanged.

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/api/routes_interact.py src/base_agent_system/api/routes_chat.py tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py
git commit -m "feat: add request correlation for opik traces"
```

### Task 5: Trace Delegated Worker Branches

**Files:**
- Modify: `src/base_agent_system/workers/tasks.py`
- Test: `tests/integration/test_arq_worker.py`
- Create: `tests/integration/test_opik_worker_tracing.py`

**Step 1: Write the failing worker tracing tests**

Cover:
- child branches create their own traces
- child trace links to `parent_interaction_id`
- parent summary behavior remains unchanged
- worker-started traces still carry `thread_id`

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py -q
```

**Step 3: Implement tracing in `run_interaction_branch(...)`**

Instrument:
- worker start
- branch run
- completion and failure
- parent-child linkage metadata

Do not change repository semantics.

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/workers/tasks.py tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py
git commit -m "feat: trace delegated worker branches"
```

### Task 6: Define Flexible Evaluation Models and Metric Registry

**Files:**
- Create: `src/base_agent_system/evaluations/__init__.py`
- Create: `src/base_agent_system/evaluations/models.py`
- Create: `src/base_agent_system/evaluations/metrics.py`
- Create: `src/base_agent_system/evaluations/registry.py`
- Test: `tests/contract/test_evaluation_metrics.py`

**Step 1: Write the failing metric tests**

Cover:
- metrics can be registered independently
- metrics can declare applicability
- metrics can be versioned
- a branch can produce multiple scores
- primitive signals and derived scores stay separate

Suggested minimal abstractions:
- `EvaluationRun`
- `MetricResult`
- `EvaluationMetric` protocol or base
- `MetricRegistry`

Starter metric families:
- `grounding`
- `completion`
- `efficiency`

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/contract/test_evaluation_metrics.py -q
```

**Step 3: Implement minimal evaluation layer**

Important constraints:
- no hardcoded single score
- metric results should include:
  - `metric_name`
  - `metric_version`
  - `score`
  - `reason`
  - optional `details`

Primitive branch signals should remain raw and reusable.

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/contract/test_evaluation_metrics.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/evaluations tests/contract/test_evaluation_metrics.py
git commit -m "feat: add extensible evaluation metric registry"
```

### Task 7: Add an Opik Evaluation Runner

**Files:**
- Create: `src/base_agent_system/evaluations/opik_runner.py`
- Optional Create: `src/base_agent_system/evaluations/datasets.py`
- Optional Test: `tests/integration/test_opik_eval_runner.py`

**Step 1: Write the failing eval-runner tests**

Cover:
- build datasets or examples from curated branch inputs
- run multiple metrics against outputs
- assign `experiment_name`
- no coupling to live API required

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/integration/test_opik_eval_runner.py -q
```

**Step 3: Implement a minimal runner**

Support:
- in-memory curated examples first
- later extension to load examples from interaction history
- one public entrypoint that can:
  - build the task
  - run metrics
  - send experiment results to Opik

Keep this runner separate from request handling code.

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/integration/test_opik_eval_runner.py -q
```

**Step 5: Commit**

```bash
git add src/base_agent_system/evaluations/opik_runner.py src/base_agent_system/evaluations/datasets.py tests/integration/test_opik_eval_runner.py
git commit -m "feat: add opik evaluation runner"
```

### Task 8: Document Local Setup and Operating Model

**Files:**
- Modify: `README.md`
- Modify: `docs/runbooks/local-development.md`
- Optional Test: `tests/smoke/test_bootstrap_docs.py`

**Step 1: Write the failing doc assertions if needed**

If this repo uses smoke tests for docs layout or content, add or update them.

**Step 2: Run tests to verify failure**

Run:
```bash
python3 -m pytest tests/smoke/test_bootstrap_docs.py -q
```

**Step 3: Update docs**

Document:
- how to enable Opik
- required env vars
- local vs hosted Opik setup
- branch trace model
- how evaluations and experiments are intended to evolve
- that metrics are extensible and versioned

**Step 4: Run tests to verify pass**

Run:
```bash
python3 -m pytest tests/smoke/test_bootstrap_docs.py -q
```

**Step 5: Commit**

```bash
git add README.md docs/runbooks/local-development.md tests/smoke/test_bootstrap_docs.py
git commit -m "docs: add opik setup and evaluation guidance"
```

### Task 9: Full Verification

**Files:**
- Verify all touched files
- Test: full suite

**Step 1: Run focused tests**

```bash
python3 -m pytest tests/integration/test_config.py tests/integration/test_opik_config.py tests/integration/test_async_workflow_service.py tests/integration/test_opik_tracing.py tests/integration/test_arq_worker.py tests/integration/test_opik_worker_tracing.py tests/contract/test_interact_api.py tests/contract/test_chat_ui_api.py tests/contract/test_chat_ui_streaming.py tests/contract/test_evaluation_metrics.py -q
```

**Step 2: Run full suite**

```bash
python3 -m pytest -q
```

**Step 3: Inspect final diff**

```bash
git status --short
git diff --stat
```

**Step 4: Commit any final fixups**

Use a new commit if needed. Do not amend unless explicitly requested.

## Implementation Notes

- Keep Opik optional and no-op when disabled.
- Prefer one observability adapter over scattered direct Opik imports.
- Do not store evaluation logic inside `WorkflowService`.
- Do not hardcode one global metric schema.
- Do not require thread-level traces to be standalone execution records.
- Keep raw runtime signals available so future metrics can be recomputed.

## Suggested Initial Metric Set

Start with a very small, versioned set:

- `grounding.support_v1`
  - checks whether answers with retrieval activity include supporting evidence or citations
- `completion.request_resolution_v1`
  - checks whether the final branch output appears to answer the user task
- `efficiency.tool_cost_v1`
  - scores based on tool count, latency, and child-branch count

Later families can add:
- hallucination risk
- delegation quality
- memory usefulness
- artifact usefulness
- cancellation correctness
- human feedback derived metrics

## Open Questions For Execution

- Whether to use hosted Opik or local or self-hosted first
- Whether to trace raw message text or only summaries and redacted content
- Whether phase 1 should include direct LangGraph callback instrumentation immediately, or only top-level branch tracing first
- Whether to expose an internal CLI command for eval runs in phase 1 or keep eval running test-only initially

## Recommendation

For execution, start with:
1. config
2. observability adapter
3. branch tracing in `WorkflowService`
4. worker tracing
5. metric registry
6. eval runner
7. docs
8. full verification
