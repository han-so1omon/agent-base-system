from pathlib import Path


def test_helmfile_layout_covers_kind_and_k3s_releases() -> None:
    helmfile = Path("helmfile.yaml.gotmpl")
    kind_values = Path("infra/helm/environments/kind/values.yaml")
    k3s_values = Path("infra/helm/environments/k3s/values.yaml")

    assert helmfile.exists()
    assert kind_values.exists()
    assert k3s_values.exists()

    helmfile_text = helmfile.read_text()
    kind_text = kind_values.read_text()
    k3s_text = k3s_values.read_text()

    assert "kind:" in helmfile_text
    assert "k3s:" in helmfile_text
    assert "infra/helm/environments/kind/values.local.yaml" in helmfile_text
    assert "name: traefik" in helmfile_text
    assert "name: neo4j" in helmfile_text
    assert "name: postgres-checkpoints" in helmfile_text
    assert "name: base-agent-system" in helmfile_text
    assert "installed: {{ .Values.installTraefik }}" in helmfile_text
    assert "namespacePolicy:" in helmfile_text
    assert "from: All" in helmfile_text
    assert "installTraefik: true" in kind_text
    assert "installTraefik: false" in k3s_text
    assert "gatewayClassName:" in kind_text
    assert "gatewayClassName:" in k3s_text
