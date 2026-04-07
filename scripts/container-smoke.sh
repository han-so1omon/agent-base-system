#!/bin/sh
set -eu

image_tag="${1:-base-agent-system:smoke}"
container_name="base-agent-system-smoke"

docker build -t "$image_tag" .
docker rm -f "$container_name" >/dev/null 2>&1 || true
docker run -d --name "$container_name" \
  -p 8000:8000 \
  -e BASE_AGENT_SYSTEM_NEO4J_URI=bolt://neo4j:7687 \
  -e BASE_AGENT_SYSTEM_POSTGRES_URI=postgresql://postgres:postgres@postgres:5432/langgraph \
  "$image_tag"

trap 'docker rm -f "$container_name" >/dev/null 2>&1 || true' EXIT

sleep 2
curl -fsS http://127.0.0.1:8000/live >/dev/null
curl -fsS http://127.0.0.1:8000/ready >/dev/null
docker run --rm "$image_tag" check-connections >/dev/null
