# Kind Bootstrap

Use this runbook to prepare a `kind` cluster before running Helmfile.

## Prerequisites

- `kind`
- `kubectl`
- `docker`
- `helm`
- `helmfile`

## What Bootstrap Does

The bootstrap script:

1. Creates the `kind` cluster if it does not already exist.
2. Publishes stable host ingress ports for the control-plane node with `extraPortMappings`.
3. Switches `kubectl` to the `kind` context.
4. Installs the Gateway API CRDs.
5. Builds the local `base-agent-system:0.1.0` image.
6. Loads that image into the kind nodes with `kind load docker-image`.
7. Stops before any Helm installs and prints the next Helmfile command.

## Run Bootstrap

```bash
./scripts/bootstrap-kind.sh
```

Optional environment variables:

```bash
export KIND_CLUSTER_NAME=base-agent-system
export GATEWAY_API_VERSION=v1.2.1
export IMAGE_TAG=base-agent-system:0.1.0
export KIND_HOST_HTTP_PORT=8000
export KIND_HOST_HTTPS_PORT=8443
```

By default, bootstrap maps:

- host `8000` -> kind control-plane node port `30080`
- host `8443` -> kind control-plane node port `30443`

That gives a stable host entrypoint for Traefik after Helmfile installs the shared Gateway.

## Next Step

After bootstrap succeeds, run Helmfile:

```bash
cp infra/helm/environments/kind/values.local.example.yaml infra/helm/environments/kind/values.local.yaml
# edit infra/helm/environments/kind/values.local.yaml with a real provider key
helmfile -e kind sync
```

Bootstrap does not install Traefik, Neo4j, Postgres, or the app. Helmfile manages all Helm installs after the cluster is ready.

## Host Access After Helmfile

After `helmfile -e kind sync`, the expected host entrypoints are:

- `http://127.0.0.1:8000`
- `https://127.0.0.1:8443`

If those ports are unavailable on the host or the cluster was created before port mappings were added, use a fallback:

```bash
kubectl port-forward -n base-agent-system svc/base-agent-system 18081:80
```

Then run smoke checks against `http://127.0.0.1:18081`.

`infra/helm/environments/kind/values.local.yaml` is ignored by git and is the intended place for local-only API keys.
