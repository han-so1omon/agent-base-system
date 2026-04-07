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
2. Switches `kubectl` to the `kind` context.
3. Installs the Gateway API CRDs.
4. Builds the local `base-agent-system:0.1.0` image.
5. Loads that image into the kind nodes with `kind load docker-image`.
6. Stops before any Helm installs and prints the next Helmfile command.

## Run Bootstrap

```bash
./scripts/bootstrap-kind.sh
```

Optional environment variables:

```bash
export KIND_CLUSTER_NAME=base-agent-system
export GATEWAY_API_VERSION=v1.2.1
export IMAGE_TAG=base-agent-system:0.1.0
```

## Next Step

After bootstrap succeeds, run Helmfile:

```bash
cp infra/helm/environments/kind/values.local.example.yaml infra/helm/environments/kind/values.local.yaml
# edit infra/helm/environments/kind/values.local.yaml with a real provider key
helmfile -e kind sync
```

Bootstrap does not install Traefik, Neo4j, Postgres, or the app. Helmfile manages all Helm installs after the cluster is ready.

`infra/helm/environments/kind/values.local.yaml` is ignored by git and is the intended place for local-only API keys.
