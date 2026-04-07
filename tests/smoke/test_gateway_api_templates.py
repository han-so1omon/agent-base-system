from pathlib import Path


def test_base_agent_system_chart_uses_gateway_api_templates() -> None:
    values = Path("infra/helm/base-agent-system/values.yaml")
    gateway = Path("infra/helm/base-agent-system/templates/gateway.yaml")
    httproute = Path("infra/helm/base-agent-system/templates/httproute.yaml")
    kind_env = Path("infra/helm/environments/kind/values.yaml")

    assert values.exists()
    assert gateway.exists()
    assert httproute.exists()
    assert kind_env.exists()

    values_text = values.read_text()
    gateway_text = gateway.read_text()
    httproute_text = httproute.read_text()
    kind_text = kind_env.read_text()

    assert "gateway:" in values_text
    assert "gatewayClassName:" in values_text
    assert "enabled:" in values_text
    assert "kind: Gateway" in gateway_text
    assert "gatewayClassName:" in gateway_text
    assert "kind: HTTPRoute" in httproute_text
    assert "parentRefs:" in httproute_text
    assert "namespace:" in httproute_text
    assert "sharedGateway:" in values_text
    assert "name:" in values_text
    assert "listenerName:" in values_text
    assert "create: false" in kind_text
    assert "namespace: traefik" in kind_text
    assert "name: traefik-gateway" in kind_text
    assert "listenerName: web" in kind_text

    ingress = Path("infra/k8s/base/ingress.yaml")
    assert not ingress.exists(), "legacy ingress manifest should be removed after Helmfile migration"
