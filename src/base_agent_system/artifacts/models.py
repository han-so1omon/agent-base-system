"""Artifact storage models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactReference:
    artifact_id: str
    storage_backend: str
    storage_uri: str
    media_type: str
    logical_role: str
    checksum: str
    metadata: dict[str, object] | None = None
