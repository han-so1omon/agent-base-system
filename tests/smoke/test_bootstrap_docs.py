from pathlib import Path


def test_kind_bootstrap_runbook_exists_and_mentions_prereqs() -> None:
    script = Path("scripts/bootstrap-kind.sh")
    runbook = Path("docs/runbooks/kind-bootstrap.md")

    assert script.exists()
    assert runbook.exists()

    script_text = script.read_text()
    runbook_text = runbook.read_text()

    assert "kind" in script_text
    assert "kubectl" in script_text
    assert "docker" in script_text
    assert "helmfile" in script_text
    assert "Gateway API CRDs" in runbook_text
    assert "base-agent-system:0.1.0" in runbook_text
    assert "kind load docker-image" in runbook_text
    assert "extraPortMappings" in script_text
    assert "KIND_HOST_HTTP_PORT" in script_text
    assert "KIND_HOST_HTTPS_PORT" in script_text
    assert "KIND_HTTP_NODE_PORT" in script_text
    assert "KIND_HTTPS_NODE_PORT" in script_text
    assert "helmfile" in runbook_text.lower()
    assert "values.local.yaml" in runbook_text
    assert "8000" in runbook_text
    assert "8443" in runbook_text
    assert "kubectl port-forward" in runbook_text
