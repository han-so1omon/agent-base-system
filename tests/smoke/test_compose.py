from pathlib import Path

import yaml

def _load_compose() -> dict:
    compose_path = Path("infra/compose/docker-compose.yml")
    assert compose_path.exists(), "compose file does not exist"
    return yaml.safe_load(compose_path.read_text())


def test_compose_defines_required_local_infrastructure_shape():
    compose = _load_compose()
    services = compose["services"]
    volumes = compose["volumes"]

    assert set(services) == {"app", "neo4j", "postgres"}
    assert "graphiti" not in services

    app = services["app"]
    neo4j = services["neo4j"]
    postgres = services["postgres"]

    assert app["image"] == "busybox:1.36"
    assert app["profiles"] == ["app"]
    assert app["command"] == ["sh", "-c", "echo 'placeholder app service for local compose shape' && sleep infinity"]

    assert neo4j["ports"] == ["7474:7474", "7687:7687"]
    assert neo4j["environment"]["NEO4J_PLUGINS"] == '["apoc"]'
    assert neo4j["volumes"] == ["neo4j_data:/data"]

    healthcheck = postgres["healthcheck"]
    assert postgres["volumes"] == ["postgres_data:/var/lib/postgresql/data"]
    assert healthcheck["test"] == ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]

    assert set(volumes) == {"neo4j_data", "postgres_data"}
