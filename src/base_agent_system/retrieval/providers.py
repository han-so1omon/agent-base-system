from __future__ import annotations

from base_agent_system.retrieval.index_service import RetrievalIndex
from base_agent_system.retrieval.models import RetrievalResult


class LocalIndexRetrievalProvider:
    def __init__(self, index: RetrievalIndex) -> None:
        self._index = index

    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]:
        return self._index.query(text, top_k=top_k)
