"""Artifact storage implementations."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from base_agent_system.artifacts.models import ArtifactReference


class LocalArtifactStorage:
    def __init__(self, *, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def write_bytes(
        self,
        *,
        logical_role: str,
        media_type: str,
        data: bytes,
        metadata: dict[str, object] | None = None,
    ) -> ArtifactReference:
        artifact_id = f"artifact-{uuid4()}"
        suffix = _suffix_for_media_type(media_type)
        path = self._base_dir / f"{artifact_id}{suffix}"
        path.write_bytes(data)
        checksum = f"sha256:{sha256(data).hexdigest()}"
        return ArtifactReference(
            artifact_id=artifact_id,
            storage_backend="local",
            storage_uri=path.as_uri(),
            media_type=media_type,
            logical_role=logical_role,
            checksum=checksum,
            metadata=metadata,
        )

    def resolve(self, reference: ArtifactReference) -> Path:
        return Path(reference.storage_uri.replace("file://", ""))


def _suffix_for_media_type(media_type: str) -> str:
    if media_type == "text/markdown":
        return ".md"
    if media_type == "application/json":
        return ".json"
    return ".bin"
