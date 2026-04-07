"""Data models for the Graphiti memory boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryEpisode:
    thread_id: str
    actor: str
    content: str


@dataclass(frozen=True)
class MemorySearchResult:
    thread_id: str
    actor: str
    content: str
    score: float
