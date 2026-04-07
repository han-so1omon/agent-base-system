from pathlib import Path


def test_neo4j_values_are_split_by_common_and_environment() -> None:
    common = Path("infra/helm/neo4j/values-common.yaml")
    kind = Path("infra/helm/neo4j/values-kind.yaml")
    k3s = Path("infra/helm/neo4j/values-k3s.yaml")
    helmfile = Path("helmfile.yaml.gotmpl")

    assert common.exists()
    assert kind.exists()
    assert k3s.exists()
    assert helmfile.exists()

    common_text = common.read_text()
    kind_text = kind.read_text()
    k3s_text = k3s.read_text()
    helmfile_text = helmfile.read_text()

    assert "neo4j:" in common_text
    assert "edition: community" in common_text
    assert "apoc_jar_enabled:" in common_text
    assert "gatewayClassName" not in common_text
    assert "values-common.yaml" in helmfile_text
    assert "values-{{ .Environment.Name }}.yaml" in helmfile_text
    assert "storageClassName" in kind_text or "storageClassName" in k3s_text
