from __future__ import annotations

from pathlib import Path


def test_local_artifact_storage_writes_bytes_and_returns_reference(tmp_path: Path) -> None:
    from base_agent_system.artifacts.storage import LocalArtifactStorage

    storage = LocalArtifactStorage(base_dir=tmp_path)

    reference = storage.write_bytes(
        logical_role="summary",
        media_type="text/markdown",
        data=b"# Report\n",
        metadata={"title": "Run Summary"},
    )

    assert reference.logical_role == "summary"
    assert reference.media_type == "text/markdown"
    assert reference.storage_backend == "local"
    assert reference.metadata == {"title": "Run Summary"}
    assert reference.checksum.startswith("sha256:")
    assert storage.resolve(reference).read_bytes() == b"# Report\n"


def test_artifact_reference_can_point_to_arbitrary_storage_locations() -> None:
    from base_agent_system.artifacts.models import ArtifactReference

    reference = ArtifactReference(
        artifact_id="artifact-123",
        storage_backend="external",
        storage_uri="s3://bucket/path/report.json",
        media_type="application/json",
        logical_role="dataset",
        checksum="sha256:abc",
        metadata={"schema": "flexible"},
    )

    assert reference.storage_backend == "external"
    assert reference.storage_uri == "s3://bucket/path/report.json"
    assert reference.metadata == {"schema": "flexible"}
