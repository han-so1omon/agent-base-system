"""Data models for retrieval results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    path: str
    snippet: str


@dataclass(frozen=True)
class RetrievalResult:
    text: str
    score: float
    citation: Citation
