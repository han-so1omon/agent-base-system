from __future__ import annotations

from base_agent_system.retrieval.models import Citation, RetrievalResult


def test_search_docs_tool_formats_grounding_payload() -> None:
    from base_agent_system.workflow.agent_tools import build_search_docs_tool

    retrieval_service = _StubRetrievalService()
    tool = build_search_docs_tool(retrieval_service)

    result = tool.invoke({"query": "what does ingestion do?"})

    assert retrieval_service.calls == [("what does ingestion do?", 3)]
    assert "docs/seed/example.md" in result
    assert "markdown ingestion service" in result


def test_search_memory_tool_uses_thread_id_and_formats_memory_payload() -> None:
    from base_agent_system.workflow.agent_tools import build_search_memory_tool

    memory_service = _StubMemoryService()
    tool = build_search_memory_tool(memory_service)

    result = tool.invoke({"thread_id": "thread-123", "query": "what deployment target did I prefer?"})

    assert memory_service.calls == [("what deployment target did I prefer?", "thread-123", 3)]
    assert "Kubernetes" in result
    assert "assistant" in result


class _StubRetrievalService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]:
        self.calls.append((text, top_k))
        return [
            RetrievalResult(
                text="The markdown ingestion service scans seed docs and builds the retrieval index.",
                score=0.98,
                citation=Citation(
                    path="docs/seed/example.md",
                    snippet="This seed document explains the markdown ingestion service.",
                ),
            )
        ]


class _StubMemoryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def search_memory(self, query: str, *, thread_id: str, limit: int = 5) -> list[dict[str, object]]:
        self.calls.append((query, thread_id, limit))
        return [
            {
                "thread_id": thread_id,
                "actor": "assistant",
                "content": "Your preferred deployment target was Kubernetes.",
                "score": 1.0,
            }
        ]
