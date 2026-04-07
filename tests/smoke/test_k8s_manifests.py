from pathlib import Path

import yaml


def _load_yaml(path: str) -> dict:
    file_path = Path(path)
    assert file_path.exists(), f"{path} is missing"
    return yaml.safe_load(file_path.read_text())


def test_k8s_base_manifests_define_app_contract() -> None:
    namespace = _load_yaml("infra/k8s/base/namespace.yaml")
    configmap = _load_yaml("infra/k8s/base/configmap.yaml")
    secret = _load_yaml("infra/k8s/base/secret.example.yaml")
    deployment = _load_yaml("infra/k8s/base/deployment.yaml")
    service = _load_yaml("infra/k8s/base/service.yaml")
    ingress = _load_yaml("infra/k8s/base/ingress.yaml")
    kustomization = _load_yaml("infra/k8s/base/kustomization.yaml")

    assert namespace["kind"] == "Namespace"
    assert namespace["metadata"]["name"] == "base-agent-system"

    assert configmap["kind"] == "ConfigMap"
    assert configmap["data"]["BASE_AGENT_SYSTEM_PORT"] == "8000"
    assert configmap["data"]["UVICORN_HOST"] == "0.0.0.0"
    assert "BASE_AGENT_SYSTEM_POSTGRES_URI" not in configmap["data"]

    assert secret["kind"] == "Secret"
    assert secret["metadata"]["name"] == "base-agent-system-secrets"
    assert secret["stringData"]["OPENAI_API_KEY"] == "replace-me"
    assert (
        secret["stringData"]["BASE_AGENT_SYSTEM_POSTGRES_URI"]
        == "postgresql://postgres:postgres@postgres-checkpoints:5432/langgraph"
    )

    spec = deployment["spec"]
    assert deployment["kind"] == "Deployment"
    assert spec["strategy"]["type"] == "RollingUpdate"

    container = spec["template"]["spec"]["containers"][0]
    assert container["name"] == "app"
    assert container["image"] == "base-agent-system:0.1.0"
    assert container["args"] == ["api"]
    assert container["ports"] == [{"containerPort": 8000, "name": "http"}]
    assert container["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/live"
    assert container["readinessProbe"]["httpGet"]["port"] == "http"
    assert container["livenessProbe"]["httpGet"]["port"] == "http"
    assert container["resources"]["requests"]["cpu"]
    assert container["resources"]["limits"]["memory"]
    assert spec["template"]["spec"]["securityContext"] == {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }

    env_from = container["envFrom"]
    assert env_from == [
        {"configMapRef": {"name": "base-agent-system-config"}},
        {"secretRef": {"name": "base-agent-system-secrets"}},
    ]

    assert service["kind"] == "Service"
    assert service["spec"]["ports"][0]["port"] == 80
    assert service["spec"]["ports"][0]["targetPort"] == "http"

    assert ingress["kind"] == "Ingress"
    assert ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]["name"] == "base-agent-system"

    assert kustomization["kind"] == "Kustomization"
    assert kustomization["namespace"] == "base-agent-system"
    assert kustomization["resources"] == [
        "namespace.yaml",
        "configmap.yaml",
        "deployment.yaml",
        "service.yaml",
        "ingress.yaml",
        "postgres-statefulset.yaml",
        "postgres-service.yaml",
    ]

    assert "secret.example.yaml" not in kustomization["resources"]
