"""LangChain tool wrappers around retrieval and memory services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langchain.tools import tool

from base_agent_system.memory.models import MemorySearchResult
from base_agent_system.retrieval.models import RetrievalResult


class RetrievalService(Protocol):
    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]: ...


class MemoryService(Protocol):
    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int = 5,
    ) -> list[MemorySearchResult | dict[str, object]]: ...


def build_search_docs_tool(
    retrieval_service: RetrievalService,
    *,
    on_result: Callable[[list[RetrievalResult]], None] | None = None,
) -> Callable[..., str]:
    @tool
    def search_docs(query: str) -> str:
        """Search indexed documents for grounded context relevant to the user query."""

        results = retrieval_service.query(query, top_k=3)
        if on_result is not None:
            on_result(results)
        if not results:
            return "No relevant documents found."

        return "\n\n".join(
            f"Source: {item.citation.path}\nSnippet: {item.citation.snippet}\nContent: {item.text}"
            for item in results
        )

    return search_docs


def build_search_memory_tool(
    memory_service: MemoryService,
    *,
    on_result: Callable[[list[MemorySearchResult | dict[str, object]]], None] | None = None,
) -> Callable[..., str]:
    @tool
    def search_memory(thread_id: str, query: str) -> str:
        """Search prior thread memory for relevant conversational context."""

        results = memory_service.search_memory(query, thread_id=thread_id, limit=3)
        if on_result is not None:
            on_result(results)
        if not results:
            return "No relevant thread memory found."

        return "\n\n".join(_format_memory_item(item) for item in results)

    return search_memory


def _format_memory_item(item: MemorySearchResult | dict[str, object]) -> str:
    if isinstance(item, dict):
        actor = str(item.get("actor", "unknown"))
        content = str(item.get("content", ""))
        score = item.get("score")
    else:
        actor = item.actor
        content = item.content
        score = item.score
    return f"Actor: {actor}\nScore: {score}\nContent: {content}"
