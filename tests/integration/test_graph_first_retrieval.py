from __future__ import annotations

from base_agent_system.config import Settings
from base_agent_system.workflow.graph import build_workflow


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        app_env="test",
    )


def test_graph_first_retrieval_queries_memory_before_docs_and_respects_policy() -> None:
    retrieval = _RecordingRetrievalService()
    memory = _RecordingMemoryService()
    workflow = build_workflow(
        settings=_settings(),
        retrieval_service=retrieval,
        memory_service=memory,
        state_graph_factory=lambda state_type: _FakeStateGraph(),
    )

    result = workflow.invoke(
        {
            "thread_id": "thread-123",
            "query": "What context is available?",
            "context_policy": {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"},
        }
    )

    assert memory.calls == [
        {
            "query": "What context is available?",
            "thread_id": "thread-123",
            "limit": 3,
            "context_policy": {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"},
        }
    ]
    assert retrieval.calls == [
        {
            "text": "What context is available?",
            "top_k": 3,
            "context_policy": {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"},
        }
    ]
    assert result["debug"]["memory_hits"] == 1
    assert result["debug"]["document_hits"] == 1


class _RecordingRetrievalService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def query(self, text: str, *, top_k: int, context_policy=None):
        self.calls.append({"text": text, "top_k": top_k, "context_policy": context_policy})
        return [
            type(
                "Result",
                (),
                {
                    "text": "Doc context",
                    "score": 1.0,
                    "citation": type("Citation", (), {"path": "docs/seed/example.md", "snippet": "Doc context"})(),
                },
            )()
        ]


class _RecordingMemoryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search_memory(self, query: str, *, thread_id: str, limit: int = 5, context_policy=None):
        self.calls.append(
            {
                "query": query,
                "thread_id": thread_id,
                "limit": limit,
                "context_policy": context_policy,
            }
        )
        return [
            type(
                "Memory",
                (),
                {"thread_id": thread_id, "actor": "user", "content": "Graph memory", "score": 1.0},
            )()
        ]

    def store_episode(self, episode):
        return None


class _FakeStateGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, object] = {}
        self._edges: list[tuple[str, str]] = []

    def add_node(self, name: str, node: object) -> None:
        self._nodes[name] = node

    def add_edge(self, start: str, end: str) -> None:
        self._edges.append((start, end))

    def compile(self, *, checkpointer=None):
        return _CompiledWorkflow(self._nodes, self._edges)


class _CompiledWorkflow:
    def __init__(self, nodes: dict[str, object], edges: list[tuple[str, str]]) -> None:
        self._nodes = nodes
        self._edges = edges

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        current_state = dict(state)
        node_name = self._next_node("START")
        while node_name != "END":
            update = self._nodes[node_name](current_state)
            current_state.update(update)
            node_name = self._next_node(node_name)
        return current_state

    def _next_node(self, start: str) -> str:
        for edge_start, edge_end in self._edges:
            if edge_start == start:
                return edge_end
        raise AssertionError(f"missing edge from {start}")
