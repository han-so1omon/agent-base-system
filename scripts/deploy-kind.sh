#!/usr/bin/env bash

set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-base-agent-system}"
NAMESPACE="${KIND_NAMESPACE:-base-agent-system}"
RELEASE_NAME="${KIND_RELEASE_NAME:-base-agent-system}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-base-agent-system}"
IMAGE_TAG="${IMAGE_TAG:-kind-$(date +%Y%m%d%H%M%S)}"
IMAGE_REF="${IMAGE_REPOSITORY}:${IMAGE_TAG}"

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing required tool: %s\n' "$tool" >&2
    exit 1
  fi
}

require_tool kind
require_tool docker
require_tool kubectl
require_tool helm

if [ ! -f "infra/helm/environments/kind/values.local.yaml" ]; then
  printf 'Missing local values file: infra/helm/environments/kind/values.local.yaml\n' >&2
  exit 1
fi

docker build -t "$IMAGE_REF" .
kind load docker-image "$IMAGE_REF" --name "$CLUSTER_NAME"

helm upgrade --install "$RELEASE_NAME" infra/helm/base-agent-system \
  -n "$NAMESPACE" \
  --create-namespace \
  --values infra/helm/environments/kind/values.yaml \
  --values infra/helm/environments/kind/values.local.yaml \
  --set image.repository="$IMAGE_REPOSITORY" \
  --set image.tag="$IMAGE_TAG"

kubectl rollout status deployment/base-agent-system -n "$NAMESPACE" --timeout=240s

printf 'Deployed %s to kind cluster %s\n' "$IMAGE_REF" "$CLUSTER_NAME"
