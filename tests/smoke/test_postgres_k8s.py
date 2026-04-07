from pathlib import Path

import yaml


def _load_yaml(path: str) -> dict:
    file_path = Path(path)
    assert file_path.exists(), f"{path} is missing"
    return yaml.safe_load(file_path.read_text())


def test_postgres_manifests_cover_checkpoint_persistence() -> None:
    statefulset = _load_yaml("infra/k8s/base/postgres-statefulset.yaml")
    service = _load_yaml("infra/k8s/base/postgres-service.yaml")
    kustomization = _load_yaml("infra/k8s/base/kustomization.yaml")
    secret = _load_yaml("infra/k8s/base/secret.example.yaml")

    assert statefulset["kind"] == "StatefulSet"
    assert statefulset["metadata"]["name"] == "postgres-checkpoints"
    container = statefulset["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "postgres:16"
    assert container["ports"] == [{"containerPort": 5432, "name": "postgres"}]
    assert container["env"][0]["name"] == "POSTGRES_DB"
    assert container["env"][0]["value"] == "langgraph"
    assert container["volumeMounts"][0]["mountPath"] == "/var/lib/postgresql/data"
    assert statefulset["spec"]["volumeClaimTemplates"][0]["spec"]["resources"]["requests"]["storage"] == "10Gi"

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "postgres-checkpoints"
    assert service["spec"]["ports"][0]["port"] == 5432

    assert (
        secret["stringData"]["BASE_AGENT_SYSTEM_POSTGRES_URI"]
        == "postgresql://postgres:postgres@postgres-checkpoints:5432/langgraph"
    )

    assert "postgres-statefulset.yaml" in kustomization["resources"]
    assert "postgres-service.yaml" in kustomization["resources"]
