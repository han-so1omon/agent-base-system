# Troubleshooting

## `/ready` returns `503`

Check that Neo4j and Postgres environment variables are present and the backing services are reachable.

If startup fails before `/ready` is available, also confirm a provider key is set for live Graphiti memory:
- `OPENAI_API_KEY`, or
- the provider env name configured in `BASE_AGENT_SYSTEM_OPENAI_API_KEY_NAME`

## App pods restart

Check the liveness probe path `/live`, image startup logs, and the app Helm chart deployment template in `infra/helm/base-agent-system/templates/deployment.yaml`.

## Checkpoint writes fail

Verify the `postgres-checkpoints` Service resolves and the StatefulSet volume is bound.

## Memory disappears after API restart

If thread memory works before restart but disappears afterward:
- confirm the API was started with the live runtime env vars, including provider key
- repeat the smoke test with the same `thread_id`
- inspect Neo4j Browser for `group_id = "smoke-thread"`

If Neo4j remains empty and memory disappears after restart, the runtime is not using live persistent memory.

## Neo4j procedures unavailable

Confirm the Helm release uses `infra/helm/neo4j/values-common.yaml` plus the environment-specific values file and that APOC is enabled there.
