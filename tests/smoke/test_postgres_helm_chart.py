from pathlib import Path


def test_postgres_helm_chart_exists_and_covers_checkpoint_persistence() -> None:
    chart = Path("infra/helm/postgres-checkpoints/Chart.yaml")
    values = Path("infra/helm/postgres-checkpoints/values.yaml")
    statefulset = Path("infra/helm/postgres-checkpoints/templates/statefulset.yaml")
    service = Path("infra/helm/postgres-checkpoints/templates/service.yaml")
    secret = Path("infra/helm/postgres-checkpoints/templates/secret.yaml")

    assert chart.exists()
    assert values.exists()
    assert statefulset.exists()
    assert service.exists()
    assert secret.exists()

    chart_text = chart.read_text()
    values_text = values.read_text()
    statefulset_text = statefulset.read_text()
    service_text = service.read_text()
    secret_text = secret.read_text()

    assert "name: postgres-checkpoints" in chart_text
    assert "database: langgraph" in values_text
    assert "user: postgres" in values_text
    assert "kind: StatefulSet" in statefulset_text
    assert "postgres-checkpoints" in statefulset_text
    assert "POSTGRES_DB" in statefulset_text
    assert "kind: Service" in service_text
    assert "postgres-checkpoints" in service_text
    assert "kind: Secret" in secret_text
    assert "POSTGRES_PASSWORD" in secret_text
