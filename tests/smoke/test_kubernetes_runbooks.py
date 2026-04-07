from pathlib import Path


def test_kubernetes_runbook_describes_helmfile_flows() -> None:
    runbook = Path("docs/runbooks/kubernetes-deployment.md")
    assert runbook.exists()

    text = runbook.read_text()

    assert "bootstrap" in text.lower()
    assert "kind" in text
    assert "k3s" in text
    assert "helmfile -e kind sync" in text
    assert "helmfile -e k3s sync" in text
    assert "Traefik" in text
    assert "Gateway" in text
    assert "/live" in text
    assert "/ready" in text
    assert "/ingest" in text
    assert "/query" in text
    assert "8000" in text
    assert "8443" in text
    assert "port-forward" in text
    assert "values.local.yaml" in text
    assert "checkpoint_writes" in text
    assert "Episodic" in text


def test_troubleshooting_and_neo4j_docs_reference_current_helm_layout() -> None:
    troubleshooting = Path("docs/runbooks/troubleshooting.md")
    neo4j_doc = Path("docs/deployment/neo4j.md")

    troubleshooting_text = troubleshooting.read_text()
    neo4j_text = neo4j_doc.read_text()

    assert "infra/helm/base-agent-system/templates/deployment.yaml" in troubleshooting_text
    assert "infra/helm/neo4j/values-common.yaml" in troubleshooting_text
    assert "infra/helm/neo4j/values-common.yaml" in neo4j_text
    assert "values.local.yaml" in neo4j_text
