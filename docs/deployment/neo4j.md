# Neo4j On Kubernetes

Use the official Neo4j Helm chart in standalone mode for the first deployment phase.

1. Use the repo-managed values layering:
   - `infra/helm/neo4j/values-common.yaml`
   - `infra/helm/neo4j/values-kind.yaml` or `infra/helm/neo4j/values-k3s.yaml`
2. Install Neo4j through `helmfile -e <environment> sync`.
3. Keep provider API keys out of tracked values files; for `kind`, place local-only app secrets in `infra/helm/environments/kind/values.local.yaml`.
4. Wait for the single Neo4j pod to become ready before verifying the app.

This configuration keeps persistence enabled and exposes APOC procedures needed by the current memory integration.
