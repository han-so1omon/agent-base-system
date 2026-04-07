# Kubernetes Deployment

Kubernetes deployment now follows a bootstrap-first and Helmfile-second flow.

## Bootstrap First

- `kind`: run `./scripts/bootstrap-kind.sh`
- `k3s`: run `./scripts/preflight-k3s.sh`

Bootstrap prepares the cluster. It does not install Helm releases.

## Kind Flow

1. Run the kind bootstrap script.
2. Confirm the host ingress ports are reserved for the kind control-plane node:

- `http://127.0.0.1:8000`
- `https://127.0.0.1:8443`

3. Confirm the local image `base-agent-system:0.1.0` was loaded into the cluster.
4. Run:

```bash
cp infra/helm/environments/kind/values.local.example.yaml infra/helm/environments/kind/values.local.yaml
# edit infra/helm/environments/kind/values.local.yaml with a real provider key
helmfile -e kind sync
```

In `kind`, Helmfile installs Traefik, Neo4j, Postgres checkpoints, and the app chart.

## K3s Flow

1. Ensure the `k3s` cluster already exists.
2. Ensure bundled Traefik is already Gateway API-capable.
3. Run the preflight script.
4. Run:

```bash
helmfile -e k3s sync
```

In `k3s`, Helmfile installs Neo4j, Postgres checkpoints, and the app chart. It does not install Traefik.

## Traefik Ownership

- `kind`: Traefik is installed by Helmfile.
- `k3s`: Traefik is assumed to already exist and be ready before Helmfile runs.

## Gateway API Validation

After deployment, verify the shared Gateway and HTTPRoute exist:

```bash
kubectl get gateway -n traefik
kubectl get httproute -n base-agent-system
```

If using `k3s`, also confirm the expected `GatewayClass` exists:

```bash
kubectl get gatewayclass
```

## Smoke Test Sequence

After releases are ready, verify the app end to end:

1. Check `GET /live`
2. Check `GET /ready`
3. Run `POST /ingest`
4. Run `POST /query`
5. Confirm Neo4j Browser is reachable and inspect persisted graph memory
6. Restart the app deployment and run `POST /query` again for the same thread
7. Confirm Neo4j and Postgres both retained data across the restart

The minimum API checks are:

- `/live` returns `200`
- `/ready` returns `200`
- `/ingest` succeeds
- `/query` succeeds

In `kind`, the preferred host entrypoint is through the bootstrap port mappings on `127.0.0.1:8000` and `127.0.0.1:8443`.

Those host ports map to stable Traefik node ports `30080` and `30443` inside the kind control-plane node.

If the cluster was created before those mappings existed, use a temporary fallback:

```bash
kubectl port-forward -n base-agent-system svc/base-agent-system 18081:80
```

Then run the smoke checks against `http://127.0.0.1:18081`.

## Kind Persistence Verification

The live `kind` verification sequence is:

1. `POST /ingest` through Traefik with `{"path":"docs/seed"}`
2. `POST /query` with a stable `thread_id`
3. restart the app deployment:

```bash
kubectl rollout restart deployment/base-agent-system -n base-agent-system
kubectl rollout status deployment/base-agent-system -n base-agent-system
```

4. run the same `POST /query` again through Traefik
5. verify Neo4j contains persisted Graphiti episodes for that thread:

```bash
kubectl exec -n base-agent-system statefulset/neo4j -- \
  cypher-shell -a neo4j://localhost:7687 -u neo4j -p change-me \
  "MATCH (n:Episodic {group_id: 'your-thread-id'}) RETURN count(n) AS episodic_count"
```

6. verify Postgres checkpoint writes exist:

```bash
kubectl exec -n base-agent-system statefulset/postgres-checkpoints -- \
  psql -U postgres -d langgraph -c "select count(*) as writes from checkpoint_writes;"
```
