# K3s Bootstrap

Use this runbook after the `k3s` cluster already exists.

## Assumptions

- `k3s` is already running.
- Bundled Traefik is already installed and configured for Gateway API.
- Helmfile does not install Traefik in `k3s`.

## What Preflight Checks

The preflight script verifies:

1. Gateway API CRDs are present.
2. The expected `GatewayClass` exists.
3. The Traefik deployment is available.

If any of those checks fail, stop there and fix the cluster before running Helmfile.

## Run Preflight

```bash
./scripts/preflight-k3s.sh
```

Optional environment variables:

```bash
export GATEWAY_CLASS_NAME=traefik
export TRAEFIK_NAMESPACE=kube-system
export TRAEFIK_SELECTOR=app.kubernetes.io/name=traefik
```

## Next Step

After preflight succeeds:

```bash
helmfile -e k3s sync
```

This installs Neo4j, Postgres checkpoints, and the app chart. It does not install Traefik in `k3s`.
