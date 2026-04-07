#!/usr/bin/env bash

set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-base-agent-system}"
GATEWAY_API_VERSION="${GATEWAY_API_VERSION:-v1.2.1}"
IMAGE_TAG="${IMAGE_TAG:-base-agent-system:0.1.0}"

ensure_helmfile_on_path() {
  if command -v helmfile >/dev/null 2>&1; then
    return
  fi

  local mise_bin="/Users/errc/.local/bin/mise"
  if [ -x "$mise_bin" ]; then
    local helmfile_path
    helmfile_path="$($mise_bin which helmfile 2>/dev/null || true)"
    if [ -n "$helmfile_path" ]; then
      export PATH="$(dirname "$helmfile_path"):$PATH"
    fi
  fi
}

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing required tool: %s\n' "$tool" >&2
    exit 1
  fi
}

ensure_helmfile_on_path

require_tool kind
require_tool kubectl
require_tool docker
require_tool helm
require_tool helmfile

if ! kind get clusters | grep -Fx "$CLUSTER_NAME" >/dev/null 2>&1; then
  kind create cluster --name "$CLUSTER_NAME"
fi

kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null

kubectl apply -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"

docker build -t "$IMAGE_TAG" .
kind load docker-image "$IMAGE_TAG" --name "$CLUSTER_NAME"

printf '\nBootstrap complete for kind cluster %s.\n' "$CLUSTER_NAME"
printf 'Next step: helmfile -e kind sync\n'
