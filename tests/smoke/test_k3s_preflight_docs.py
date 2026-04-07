from pathlib import Path


def test_k3s_preflight_docs_describe_gateway_assumptions() -> None:
    script = Path("scripts/preflight-k3s.sh")
    runbook = Path("docs/runbooks/k3s-bootstrap.md")

    assert script.exists()
    assert runbook.exists()

    script_text = script.read_text()
    runbook_text = runbook.read_text()

    assert "GatewayClass" in script_text
    assert "gateway.networking.k8s.io" in script_text
    assert "Traefik" in runbook_text
    assert "Gateway API" in runbook_text
    assert "helmfile -e k3s sync" in runbook_text
    assert "does not install Traefik" in runbook_text
