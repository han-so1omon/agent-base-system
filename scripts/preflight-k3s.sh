#!/usr/bin/env bash

set -euo pipefail

# Fail fast unless the expected GatewayClass and bundled Traefik are already ready.
GATEWAY_CLASS_NAME="${GATEWAY_CLASS_NAME:-traefik}"
TRAEFIK_NAMESPACE="${TRAEFIK_NAMESPACE:-kube-system}"
TRAEFIK_SELECTOR="${TRAEFIK_SELECTOR:-app.kubernetes.io/name=traefik}"

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

require_tool kubectl
require_tool helmfile

kubectl get crd gateways.gateway.networking.k8s.io >/dev/null
kubectl get crd httproutes.gateway.networking.k8s.io >/dev/null
kubectl get gatewayclass "$GATEWAY_CLASS_NAME" >/dev/null
kubectl wait \
  --namespace "$TRAEFIK_NAMESPACE" \
  --for=condition=available deployment \
  -l "$TRAEFIK_SELECTOR" \
  --timeout=120s >/dev/null

printf 'k3s preflight passed. Bundled Traefik appears Gateway API-capable.\n'
printf 'Next step: helmfile -e k3s sync\n'
