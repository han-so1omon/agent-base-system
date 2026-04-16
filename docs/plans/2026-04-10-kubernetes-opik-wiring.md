# Self-Hosted Kubernetes Opik Deployment And Wiring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy self-hosted Opik into Kubernetes for local `kind` by default, keep `k3s` Opik enablement admin-only via private overlay, and wire `base-agent-system` to the deployed Opik instance for in-cluster tracing and smoke testing.

**Architecture:** Treat Opik as a separate platform dependency managed by its own Helmfile section and Helm chart, not as just app env wiring. The shared Helmfile should support an opt-in Opik section that is enabled by default for `kind` and disabled in shared `k3s` config. `base-agent-system` then consumes the deployed Opik endpoint through Helm-managed env and secrets.

**Tech Stack:** Helmfile, Helm, Kubernetes, official `opik/opik` Helm chart, `base-agent-system` Helm chart, kind, k3s, FastAPI app env config, Opik Python SDK

---

## Scope

This revised plan should deliver:
- an Opik-specific Helmfile/config area using the official Opik chart
- shared Helmfile architecture that can include Opik conditionally
- `kind` default enablement of self-hosted Opik in shared tracked config
- `k3s` shared config that keeps Opik off by default
- documented private overlay guidance for `k3s` admins
- `base-agent-system` chart env wiring to the deployed Opik instance
- version compatibility policy between deployed Opik and Python SDK
- Kubernetes-native smoke tests for both the Opik deployment and app integration

This revised plan should not deliver:
- default shared `k3s` Opik deployment
- production-specific secrets in repo
- advanced Opik replication/backup unless required for phase 1
- a redesign of the app Helm chart structure

## Required Correction To The Previous Plan

The earlier Kubernetes Opik plan was insufficient because it only covered app-side env wiring. This revised plan expands scope to include:
- installing the official Opik chart
- deciding namespace and connectivity
- defining version compatibility
- validating the Opik platform itself before validating app traces

## Deployment Model

Recommended model:
- `kind`
  - self-hosted Opik enabled by default in shared tracked config
  - used for end-to-end local validation
- `k3s`
  - Opik disabled in shared tracked config
  - private admin overlay can enable and configure it
- `base-agent-system`
  - talks to Opik over an internal cluster address
- humans
  - access Opik UI via ingress or port-forward

Recommended phase-1 storage/access posture for Opik:
- use the official `opik/opik` chart
- use chart defaults where reasonable
- avoid advanced replication/backup in phase 1
- use simple frontend ingress or port-forward for validation
- document bundled ClickHouse assumptions explicitly

## Version Policy

The plan must explicitly pin and verify:
- deployed Opik chart/app version
- Python `opik` package version in `pyproject.toml`

Because Opik’s docs warn that Kubernetes deployment version and Python SDK version should match, version compatibility must be a first-class acceptance criterion.

## Planned Files

**Modify**
- root/shared Helmfile files once exact filenames are confirmed
- `infra/helm/base-agent-system/values.yaml`
- `infra/helm/base-agent-system/templates/configmap.yaml`
- `infra/helm/base-agent-system/templates/secret.yaml`
- `infra/helm/environments/kind/values.yaml`
- `infra/helm/environments/kind/values.local.example.yaml`
- `infra/helm/environments/k3s/values.yaml`
- `docs/runbooks/kubernetes-deployment.md`
- `docs/runbooks/kind-bootstrap.md`
- possibly `pyproject.toml` if version pin adjustment is required

**Create**
- Opik-specific Helmfile/config file(s) in repo, exact path to be chosen during execution
- optional Opik values file for shared `kind`
- optional Opik runbook if keeping Kubernetes deployment doc concise is cleaner
- tests or smoke assertions covering Helm render/deployment contract if missing

### Task 1: Audit Helmfile Topology And Choose Opik Include Pattern

**Files:**
- Read and then modify the repo’s shared Helmfile entrypoints
- Test: existing Helmfile-related smoke tests if any

**Step 1: Write the failing test or checklist**
- If Helmfile structure is already test-covered, add a failing assertion for an Opik include path.
- Otherwise create a checklist-driven task with exact target files after inspection.

**Step 2: Inspect current Helmfile structure**
Run:
```bash
glob "**/*helmfile*.{yaml,yml,gotmpl}" .
read the root/shared Helmfile files
```

Expected:
- identify the shared Helmfile entrypoint
- identify environment selectors for `kind` and `k3s`

**Step 3: Choose the minimal include pattern**
Recommended:
- shared Helmfile references an Opik-specific Helmfile section/file
- inclusion controlled by environment values
- `kind` shared config enables it
- `k3s` shared config leaves it off

**Step 4: Verify planned include structure**
- confirm the chosen include mechanism works with current Helmfile conventions
- avoid inventing a second orchestration pattern if one already exists

**Step 5: Commit**
```bash
git add <shared helmfile files>
git commit -m "feat: add optional helmfile hook for opik"
```

### Task 2: Add Opik-Specific Helmfile And Pin Deployment Version

**Files:**
- Create: dedicated Opik Helmfile/config file(s)
- Modify: shared Helmfile include points
- Modify: tracked `kind` config files
- Test: Helmfile render/structure validation if present

**Step 1: Write the failing render/assertion test**
Add or update assertions that:
- the `kind` environment includes Opik by default
- `k3s` shared config does not
- the Opik chart version/app version is pinned, not floating on `latest`

**Step 2: Run test to verify failure**
Run:
```bash
python3 -m pytest <helmfile or deployment smoke tests> -q
```

**Step 3: Implement the Opik Helmfile**
Use the official `opik/opik` chart.
Do not use `latest`.
Capture:
- Helm repo
- chart name
- namespace, likely `opik`
- pinned version
- core values path(s)

**Step 4: Add environment policy**
- `kind`: enable Opik in tracked shared config
- `k3s`: keep disabled in tracked shared config

**Step 5: Run verification**
Use either Helmfile lint/render or any existing test harness.

**Step 6: Commit**
```bash
git add <opik helmfile files> <shared helmfile files> <kind and k3s env files>
git commit -m "feat: add self-hosted opik helm deployment"
```

### Task 3: Define Opik Access Model And Base Values

**Files:**
- Create or modify Opik values files
- Modify: deployment docs later
- Test: Helm render inspection

**Step 1: Write the failing render assertion**
Assert that the chosen Opik release exposes a known access path for:
- app-to-Opik traffic
- human UI access

**Step 2: Choose connectivity model**
Recommended:
- app uses internal cluster address/service
- humans use ingress or port-forward for the Opik frontend

Avoid making the app depend on the public ingress URL if internal service routing is available.

**Step 3: Implement minimal Opik values**
Phase-1 values should cover:
- namespace
- frontend access model
- any required defaults for bundled ClickHouse
- no advanced backup/replication unless needed

**Step 4: Run render verification**
Run Helm template for the Opik release and confirm:
- frontend exposure path exists
- backend components are present
- chart values are syntactically valid

**Step 5: Commit**
```bash
git add <opik values files>
git commit -m "feat: configure opik cluster access model"
```

### Task 4: Add App-Side Helm Wiring To The Deployed Opik Instance

**Files:**
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/base-agent-system/templates/configmap.yaml`
- Modify: `infra/helm/base-agent-system/templates/secret.yaml`
- Modify: `infra/helm/environments/kind/values.yaml`
- Modify: `infra/helm/environments/kind/values.local.example.yaml`
- Modify: `infra/helm/environments/k3s/values.yaml`
- Test: `tests/smoke/test_container_contract.py` or equivalent

**Step 1: Write the failing chart contract test**
Assert:
- app chart exposes Opik env vars
- app secret exposes `OPIK_API_KEY`
- default app chart remains disabled/safe without Opik
- `kind` tracked config points to the deployed Opik instance
- `k3s` tracked config keeps app-side Opik disabled unless overridden privately

**Step 2: Run test to verify failure**
Run:
```bash
python3 -m pytest tests/smoke/test_container_contract.py -q
```

**Step 3: Implement values and templates**
ConfigMap:
- `BASE_AGENT_SYSTEM_OPIK_ENABLED`
- `BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME`
- `BASE_AGENT_SYSTEM_OPIK_WORKSPACE`
- `BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME`
- `BASE_AGENT_SYSTEM_OPIK_URL`
- `BASE_AGENT_SYSTEM_OPIK_USE_LOCAL`

Secret:
- `OPIK_API_KEY`

Important:
- `BASE_AGENT_SYSTEM_OPIK_URL` must now point at the deployed Opik instance, not an unspecified placeholder

**Step 4: Run test to verify pass**
Run:
```bash
python3 -m pytest tests/smoke/test_container_contract.py -q
```

**Step 5: Commit**
```bash
git add infra/helm/base-agent-system/values.yaml infra/helm/base-agent-system/templates/configmap.yaml infra/helm/base-agent-system/templates/secret.yaml infra/helm/environments/kind/values.yaml infra/helm/environments/kind/values.local.example.yaml infra/helm/environments/k3s/values.yaml tests/smoke/test_container_contract.py
git commit -m "feat: wire app chart to deployed opik"
```

### Task 5: Pin And Verify Opik Version Compatibility

**Files:**
- Modify: `pyproject.toml` if the Python `opik` dependency needs pinning or narrowing
- Modify: Opik Helmfile/config files
- Modify: docs

**Step 1: Write the failing compatibility test or assertion**
Assert or document-check that:
- the deployed Opik version is pinned
- the Python `opik` SDK version is pinned or constrained compatibly
- docs mention keeping them aligned

**Step 2: Run the test/check to verify failure**
Use existing dependency/config tests if available, otherwise a docs/config contract test.

**Step 3: Implement version alignment**
- pin the Opik chart/app version in deployment config
- verify or tighten the Python `opik` package version if necessary
- document the compatibility rule

**Step 4: Run verification**
Run relevant tests plus any dependency contract test.

**Step 5: Commit**
```bash
git add pyproject.toml <opik helm files> <docs/tests>
git commit -m "fix: align opik deployment and sdk versions"
```

### Task 6: Document Kind Default Enablement And K3s Admin Overlay Policy

**Files:**
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Modify: `docs/runbooks/kind-bootstrap.md`
- Modify: `docs/runbooks/local-development.md` if needed for contrast
- Optional Create: dedicated Opik deployment runbook
- Test: `tests/smoke/test_kubernetes_runbooks.py`
- Optional Test: `tests/smoke/test_bootstrap_docs.py`

**Step 1: Write the failing docs test**
Assert docs now state:
- self-hosted Opik is deployed in `kind` by default through shared tracked config
- `k3s` Opik is admin-only via private overlay
- the app no longer relies on manual shell exports for deployed smoke tests
- `values.local.yaml` is used for local secrets in `kind`

**Step 2: Run test to verify failure**
Run:
```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py tests/smoke/test_bootstrap_docs.py -q
```

**Step 3: Update docs**
Document:
- Helmfile includes Opik for `kind`
- how to access the Opik UI in `kind`
- where to place local Opik secrets
- `k3s` private overlay expectations for admins only
- difference between local direct-run env setup and deployed env setup

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py tests/smoke/test_bootstrap_docs.py -q
```

**Step 5: Commit**
```bash
git add docs/runbooks/kubernetes-deployment.md docs/runbooks/kind-bootstrap.md docs/runbooks/local-development.md tests/smoke/test_kubernetes_runbooks.py tests/smoke/test_bootstrap_docs.py
git commit -m "docs: add self-hosted opik kubernetes guidance"
```

### Task 7: Add End-To-End Kubernetes Smoke Test Checklist

**Files:**
- Modify: `docs/runbooks/kubernetes-deployment.md`
- Optional Create: `docs/runbooks/opik-smoke.md`
- Test: docs smoke assertions if available

**Step 1: Write the failing docs assertion**
Assert the smoke flow includes both layers:
- Opik platform validation
- app trace validation

Expected flow:
1. deploy or sync Helmfile
2. verify Opik release healthy
3. verify Opik frontend reachable
4. verify app deployment healthy
5. verify app pod has Opik env
6. run `/interact`
7. run same-thread `/interact`
8. run `/api/chat`
9. verify traces arrive in self-hosted Opik

**Step 2: Run test to verify failure**
Run:
```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

**Step 3: Update runbook**
Include exact checks like:
```bash
kubectl get pods -n opik
kubectl port-forward -n opik svc/opik-frontend 5173
kubectl exec -n base-agent-system deploy/base-agent-system -- env | grep OPIK
kubectl rollout status deployment/base-agent-system -n base-agent-system
```

Then include the app smoke requests and the Opik UI validation checklist.

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/smoke/test_kubernetes_runbooks.py -q
```

**Step 5: Commit**
```bash
git add docs/runbooks/kubernetes-deployment.md tests/smoke/test_kubernetes_runbooks.py
git commit -m "docs: add self-hosted opik smoke flow"
```

### Task 8: Validate End-To-End In Kind

**Files:**
- Verify all touched Helm/config/docs files
- Optional scripts if a real operational gap is discovered

**Step 1: Run focused tests**
Run:
```bash
python3 -m pytest tests/smoke/test_container_contract.py tests/smoke/test_kubernetes_runbooks.py tests/smoke/test_bootstrap_docs.py -q
```

**Step 2: Render both releases**
Render:
- Opik release
- `base-agent-system` release

Verify:
- Opik manifests are valid
- app chart points at deployed Opik
- expected ConfigMap/Secret keys exist

**Step 3: Optional live kind validation**
If cluster is available:
```bash
./scripts/bootstrap-kind.sh
helmfile -e kind sync
kubectl get pods -n opik
kubectl rollout status deployment/base-agent-system -n base-agent-system
kubectl exec -n base-agent-system deploy/base-agent-system -- env | grep OPIK
```

Then:
- access Opik UI through documented path
- run `/interact`
- run `/api/chat`
- verify traces appear in Opik grouped correctly

**Step 4: Run broader regression checks**
Run:
```bash
python3 -m pytest -q
```

**Step 5: Commit any final fixups**
Use a new commit if needed. Do not amend unless explicitly requested.

## Implementation Notes

- Use the official `opik/opik` Helm chart.
- Do not use floating `latest` versions.
- Keep Opik deployment concerns separate from app chart concerns.
- `kind` is the tracked shared environment for self-hosted Opik validation.
- `k3s` remains private/admin-only for Opik deployment enablement.
- Prefer internal cluster connectivity from app to Opik.
- Keep bundled ClickHouse assumptions explicit in docs.
- Do not overdesign phase-1 backup/replication unless required.

## Key Audit Corrections From Opik Kubernetes Docs

This revised plan fixes the gaps in the earlier plan by explicitly covering:
- official Helm-based Opik installation
- Opik namespace/release management
- frontend access path
- storage/backend assumptions
- version compatibility between deployed Opik and Python SDK

## Open Questions For Execution

- exact shared Helmfile filenames and include mechanism
- whether Opik UI in `kind` should be documented via ingress, port-forward, or both
- whether bundled ClickHouse is acceptable for phase 1 in `kind`
- whether to create a separate Opik runbook or keep everything in `kubernetes-deployment.md`

## Recommendation

For execution, do it in this order:
1. Helmfile include architecture
2. Opik Helm deployment
3. version pinning/compatibility
4. app chart wiring
5. docs and environment policy
6. smoke flow
7. live `kind` validation
