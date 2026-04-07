from pathlib import Path


def test_base_agent_system_helm_chart_exists_and_covers_app_contract() -> None:
    chart = Path("infra/helm/base-agent-system/Chart.yaml")
    values = Path("infra/helm/base-agent-system/values.yaml")
    deployment = Path("infra/helm/base-agent-system/templates/deployment.yaml")
    service = Path("infra/helm/base-agent-system/templates/service.yaml")
    configmap = Path("infra/helm/base-agent-system/templates/configmap.yaml")
    secret = Path("infra/helm/base-agent-system/templates/secret.yaml")

    assert chart.exists()
    assert values.exists()
    assert deployment.exists()
    assert service.exists()
    assert configmap.exists()
    assert secret.exists()

    chart_text = chart.read_text()
    values_text = values.read_text()
    deployment_text = deployment.read_text()
    service_text = service.read_text()
    configmap_text = configmap.read_text()
    secret_text = secret.read_text()

    assert "name: base-agent-system" in chart_text
    assert "repository:" in values_text
    assert "tag: 0.1.0" in values_text
    assert "kind: Deployment" in deployment_text
    assert "/ready" in deployment_text
    assert "/live" in deployment_text
    assert "envFrom" in deployment_text
    assert "kind: Service" in service_text
    assert "targetPort: http" in service_text
    assert "kind: ConfigMap" in configmap_text
    assert "BASE_AGENT_SYSTEM_NEO4J_URI" in configmap_text
    assert "kind: Secret" in secret_text
    assert "OPENAI_API_KEY" in secret_text
    assert "runAsUser:" in deployment_text
    assert "runAsGroup:" in deployment_text
    assert "runAsNonRoot: true" in deployment_text
    assert "readOnlyRootFilesystem: true" in deployment_text
    assert "mountPath: /tmp" in deployment_text
    assert "emptyDir: {}" in deployment_text


def test_container_image_declares_non_root_user() -> None:
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists()

    text = dockerfile.read_text()

    assert "USER " in text
