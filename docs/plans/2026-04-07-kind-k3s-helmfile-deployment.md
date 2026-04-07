# Kind And K3s Helmfile Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the application, Postgres checkpoints, and Neo4j to `kind` first and later `k3s` using Helmfile, shared Helm charts, Gateway API, and environment-specific values.

**Architecture:** Keep cluster bootstrap separate from release installation. A bootstrap script and runbook prepare the cluster, install Gateway API CRDs, and load the local app image into `kind`; Helmfile starts only after the cluster exists. Helmfile manages Traefik in `kind`, skips Traefik in `k3s`, installs Neo4j through the official chart with repo-managed values, installs a first-party Postgres chart, and installs a first-party app chart that owns a shared `Gateway` and `HTTPRoute`.

**Tech Stack:** Helmfile, Helm, Kubernetes Gateway API, Traefik, Neo4j Helm chart, Postgres, kind, k3s

---

### Task 1: Add Kind Bootstrap Script And Runbook

**Files:**
- Create: `scripts/bootstrap-kind.sh`
- Create: `docs/runbooks/kind-bootstrap.md`
- Test: `tests/smoke/test_bootstrap_docs.py`

**Step 1: Write the failing test**

Add a smoke test that asserts:
- `scripts/bootstrap-kind.sh` exists
- `docs/runbooks/kind-bootstrap.md` exists
- the runbook mentions:
  - creating a kind cluster
  - installing Gateway API CRDs
  - building/loading `base-agent-system:0.1.0`
  - running Helmfile after bootstrap

Example:

```python
from pathlib import Path

def test_kind_bootstrap_runbook_exists_and_mentions_prereqs() -> None:
    runbook = Path("docs/runbooks/kind-bootstrap.md")
    assert runbook.exists()
    text = runbook.read_text()
    assert "Gateway API CRDs" in text
    assert "helmfile" in text.lower()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_bootstrap_docs.py -q
```

Expected: FAIL because the files do not exist yet.

**Step 3: Write minimal implementation**

Create `scripts/bootstrap-kind.sh` that:
- verifies `kind`, `kubectl`, `docker`, `helm`, and `helmfile` are installed
- creates the `kind` cluster if missing
- installs Gateway API CRDs
- builds `base-agent-system:0.1.0`
- loads the image into the kind cluster
- prints the next `helmfile` command instead of installing anything directly

Create `docs/runbooks/kind-bootstrap.md` that documents:
- prerequisites
- the bootstrap script
- what the script does
- what command to run next with Helmfile

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_bootstrap_docs.py -q
```

Expected: PASS

### Task 2: Add Helmfile Skeleton With Kind And K3s Environments

**Files:**
- Create: `helmfile.yaml`
- Create: `infra/helm/environments/kind/values.yaml`
- Create: `infra/helm/environments/k3s/values.yaml`
- Test: `tests/smoke/test_helmfile_layout.py`

**Step 1: Write the failing test**

Add a smoke test that asserts:
- `helmfile.yaml` exists
- `kind` and `k3s` environments exist
- there are releases for:
  - `traefik`
  - `neo4j`
  - `postgres-checkpoints`
  - `base-agent-system`

The test should also assert that the `traefik` release is conditioned so it can be enabled in `kind` and disabled in `k3s`.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_helmfile_layout.py -q
```

Expected: FAIL because Helmfile files do not exist yet.

**Step 3: Write minimal implementation**

Create `helmfile.yaml` with:
- environment definitions for `kind` and `k3s`
- shared repositories for Traefik and Neo4j
- releases:
  - `traefik` using the official chart, conditional on environment values
  - `neo4j` using the official chart plus repo-managed values files
  - `postgres-checkpoints` using the local chart path
  - `base-agent-system` using the local chart path

Create environment values files with:
- `kind`
  - `installTraefik: true`
  - `gatewayClassName`
  - image tag/pull policy values suitable for kind
- `k3s`
  - `installTraefik: false`
  - expected `gatewayClassName`
  - registry-based image values

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_helmfile_layout.py -q
```

Expected: PASS

### Task 3: Create Postgres Helm Chart

**Files:**
- Create: `infra/helm/postgres-checkpoints/Chart.yaml`
- Create: `infra/helm/postgres-checkpoints/values.yaml`
- Create: `infra/helm/postgres-checkpoints/templates/statefulset.yaml`
- Create: `infra/helm/postgres-checkpoints/templates/service.yaml`
- Create: `infra/helm/postgres-checkpoints/templates/secret.yaml`
- Test: `tests/smoke/test_postgres_helm_chart.py`

**Step 1: Write the failing test**

Add a smoke test that asserts the chart exists and renders the expected resources:
- Service named `postgres-checkpoints`
- StatefulSet named `postgres-checkpoints`
- database defaults to `langgraph`
- credentials are supplied from chart values/secret

Prefer a test that inspects the chart files directly if Helm template rendering is not already part of the repo test setup.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_postgres_helm_chart.py -q
```

Expected: FAIL because the chart does not exist yet.

**Step 3: Write minimal implementation**

Convert the current Postgres manifest intent into a Helm chart:
- StatefulSet
- Service
- Secret
- configurable storage request
- configurable image and credentials

Keep it single-instance and minimal.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_postgres_helm_chart.py -q
```

Expected: PASS

### Task 4: Create Base Agent System Helm Chart

**Files:**
- Create: `infra/helm/base-agent-system/Chart.yaml`
- Create: `infra/helm/base-agent-system/values.yaml`
- Create: `infra/helm/base-agent-system/templates/deployment.yaml`
- Create: `infra/helm/base-agent-system/templates/service.yaml`
- Create: `infra/helm/base-agent-system/templates/configmap.yaml`
- Create: `infra/helm/base-agent-system/templates/secret.yaml`
- Test: `tests/smoke/test_base_agent_system_helm_chart.py`

**Step 1: Write the failing test**

Add a smoke test that asserts the app chart exists and captures the current deployment contract:
- Deployment
- Service
- ConfigMap
- Secret reference pattern
- pinned image value support
- readiness probe on `/ready`
- liveness probe on `/live`

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_base_agent_system_helm_chart.py -q
```

Expected: FAIL because the chart does not exist yet.

**Step 3: Write minimal implementation**

Convert the current app manifest behavior into Helm templates.

Include values for:
- image repository/tag/pullPolicy
- replica count
- resources
- env/config values
- provider secret keys

Do not add unrelated features.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_base_agent_system_helm_chart.py -q
```

Expected: PASS

### Task 5: Replace Ingress With Gateway API Templates

**Files:**
- Create: `infra/helm/base-agent-system/templates/gateway.yaml`
- Create: `infra/helm/base-agent-system/templates/httproute.yaml`
- Modify: `infra/helm/base-agent-system/values.yaml`
- Test: `tests/smoke/test_gateway_api_templates.py`

**Step 1: Write the failing test**

Add a smoke test that asserts the app chart defines:
- a shared `Gateway`
- an `HTTPRoute`
- configurable `gatewayClassName`
- configurable hostname

The test should also assert that legacy Ingress is no longer the app exposure model in the Helm path.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_gateway_api_templates.py -q
```

Expected: FAIL because the Gateway API templates do not exist yet.

**Step 3: Write minimal implementation**

Create Helm templates for:
- `Gateway`
- `HTTPRoute`

Values should control:
- `gateway.enabled`
- `gatewayClassName`
- listener hostname
- listener port/protocol

The chart should own a shared Gateway resource as requested.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_gateway_api_templates.py -q
```

Expected: PASS

### Task 6: Add Neo4j Official Chart Values Workflow

**Files:**
- Create: `infra/helm/neo4j/values-common.yaml`
- Create: `infra/helm/neo4j/values-kind.yaml`
- Create: `infra/helm/neo4j/values-k3s.yaml`
- Modify: `helmfile.yaml`
- Test: `tests/smoke/test_neo4j_helm_values_layout.py`

**Step 1: Write the failing test**

Add a smoke test that asserts:
- the values files exist
- `values-common.yaml` contains the shared Neo4j configuration
- environment values files exist and are environment-specific
- Helmfile references the official Neo4j chart and the values layering

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_neo4j_helm_values_layout.py -q
```

Expected: FAIL because the new values layout is not present yet.

**Step 3: Write minimal implementation**

Move the current Neo4j values into:
- shared values file
- environment overrides for kind/k3s

Keep using the official Neo4j Helm chart.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_neo4j_helm_values_layout.py -q
```

Expected: PASS

### Task 7: Add K3s Preflight And Runbook

**Files:**
- Create: `docs/runbooks/k3s-bootstrap.md`
- Create: `scripts/preflight-k3s.sh`
- Test: `tests/smoke/test_k3s_preflight_docs.py`

**Step 1: Write the failing test**

Add a smoke test that asserts the runbook/preflight files exist and document:
- `k3s` cluster must already exist
- bundled Traefik must already be Gateway API-capable
- Helmfile does not install Traefik in `k3s`
- deployment should fail fast if expected `GatewayClass` is missing

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_k3s_preflight_docs.py -q
```

Expected: FAIL because the files do not exist yet.

**Step 3: Write minimal implementation**

Create a small `scripts/preflight-k3s.sh` that checks:
- Gateway API CRDs present
- expected `GatewayClass` exists
- Traefik controller is present/ready

Create `docs/runbooks/k3s-bootstrap.md` documenting:
- cluster assumptions
- enabling/configuring bundled Traefik for Gateway API outside Helmfile
- preflight command
- Helmfile command

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_k3s_preflight_docs.py -q
```

Expected: PASS

### Task 8: Add Helmfile Deployment Runbooks And Smoke Test Instructions

**Files:**
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Possibly modify: `README.md`
- Test: `tests/smoke/test_kubernetes_runbooks.py`

**Step 1: Write the failing test**

Add a smoke test that asserts the Kubernetes deployment docs now explain:
- bootstrap first, Helmfile second
- `kind` flow
- `k3s` flow
- Traefik ownership difference
- Gateway API validation
- smoke test sequence after install

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: FAIL because the docs still describe the old kustomize-first model.

**Step 3: Write minimal implementation**

Update the runbook to describe:
- `kind` bootstrap script
- Helmfile environment commands such as:

```bash
helmfile -e kind sync
helmfile -e k3s sync
```

- post-deploy checks:
  - Gateway/GatewayClass
  - app readiness
  - ingest/query smoke tests
  - Neo4j Browser access

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS

### Task 9: Full Verification

**Files:**
- Verify all new charts, Helmfile files, scripts, tests, and docs

**Step 1: Run focused smoke tests**

```bash
python3 -m pytest tests/smoke/test_bootstrap_docs.py tests/smoke/test_helmfile_layout.py tests/smoke/test_postgres_helm_chart.py tests/smoke/test_base_agent_system_helm_chart.py tests/smoke/test_gateway_api_templates.py tests/smoke/test_neo4j_helm_values_layout.py tests/smoke/test_k3s_preflight_docs.py tests/smoke/test_kubernetes_runbooks.py -q
```

Expected: PASS

**Step 2: Run full suite**

```bash
python3 -m pytest tests -q
```

Expected: PASS

**Step 3: Manual kind flow verification**

Run:

```bash
./scripts/bootstrap-kind.sh
helmfile -e kind sync
```

Then verify:
- Traefik release ready
- Neo4j release ready
- Postgres release ready
- app release ready
- Gateway and HTTPRoute admitted
- app reachable through Gateway path
- `/live` and `/ready` return `200`
- `/ingest` succeeds
- `/query` succeeds
- memory survives restart and appears in Neo4j Browser

**Step 4: Manual k3s flow verification**

Run:

```bash
./scripts/preflight-k3s.sh
helmfile -e k3s sync
```

Then verify the same app smoke sequence.

### Success Criteria

- Helmfile is the top-level deploy interface for both environments
- bootstrap is separate from Helm installs
- `kind` installs Traefik through Helmfile
- `k3s` skips Traefik and fails fast if built-in Traefik is not Gateway API-capable
- the app chart owns a shared `Gateway` and `HTTPRoute`
- Neo4j uses the official chart plus repo-managed values files
- Postgres and app use first-party Helm charts
- docs clearly explain bootstrap, Helmfile usage, and smoke tests
