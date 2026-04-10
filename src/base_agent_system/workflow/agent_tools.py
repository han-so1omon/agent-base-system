"""LangChain tool wrappers around retrieval and memory services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langchain.tools import StructuredTool, tool

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


class FirecrawlClientProtocol(Protocol):
    def scrape(self, url: str) -> str: ...
    async def ascrape(self, url: str) -> str: ...
    def search(self, query: str) -> str: ...
    async def asearch(self, query: str) -> str: ...
    def crawl(self, url: str) -> str: ...
    async def acrawl(self, url: str) -> str: ...
    def crawl_status(self, job_id: str) -> str: ...
    async def acrawl_status(self, job_id: str) -> str: ...


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


def build_firecrawl_scrape_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    def firecrawl_scrape(url: str) -> str:
        """Scrape a specific URL and return its clean markdown content."""
        try:
            return client.scrape(url)
        except Exception as e:
            return f"Scrape failed: {e}"

    async def firecrawl_scrape_async(url: str) -> str:
        try:
            return await client.ascrape(url)
        except Exception as e:
            return f"Scrape failed: {e}"

    return StructuredTool.from_function(
        func=firecrawl_scrape,
        coroutine=firecrawl_scrape_async,
        name="firecrawl_scrape",
        description="Scrape a specific URL and return its clean markdown content.",
    )


def build_firecrawl_search_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_search(query: str) -> str:
        """Search the web for a query and return markdown content of top results."""
        try:
            return client.search(query)
        except Exception as e:
            return f"Search failed: {e}"

    return firecrawl_search


def build_firecrawl_crawl_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_crawl(url: str) -> str:
        """Start an asynchronous site crawl. Returns a job ID to check status later."""
        try:
            return f"Started crawl. Job ID: {client.crawl(url)}"
        except Exception as e:
            return f"Crawl failed: {e}"

    return firecrawl_crawl


def build_firecrawl_status_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_status(job_id: str) -> str:
        """Check the status of an asynchronous crawl using its job ID."""
        try:
            return client.crawl_status(job_id)
        except Exception as e:
            return f"Status check failed: {e}"

    return firecrawl_status
