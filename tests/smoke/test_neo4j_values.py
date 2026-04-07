from pathlib import Path

import yaml


def test_neo4j_values_target_standalone_helm_deployment() -> None:
    values_path = Path("infra/k8s/helm-values/neo4j.values.yaml")
    assert values_path.exists(), "neo4j values file is missing"

    values = yaml.safe_load(values_path.read_text())

    assert values["neo4j"]["name"] == "neo4j"
    assert values["neo4j"]["password"] == "change-me"
    assert values["neo4j"]["edition"] == "community"
    assert values["neo4j"]["minimumClusterSize"] == 1
    assert values["volumes"]["data"]["mode"] == "defaultStorageClass"
    assert values["config"]["dbms.security.procedures.unrestricted"] == ""
    assert values["config"]["dbms.security.procedures.allowlist"] == "apoc.coll.*,apoc.load.json.*,apoc.path.*"
    assert "apoc" in values["apoc_jar_enabled"]
