from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from base_agent_system.config import Settings
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.runtime_services import _InMemoryGraphitiBackend, build_runtime_services


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )


def test_graphiti_memory_service_requires_neo4j_configuration() -> None:
    settings = replace(_settings(), neo4j_user=" ")

    with pytest.raises(ValueError) as exc_info:
        GraphitiMemoryService(settings=settings)

    assert "neo4j" in str(exc_info.value).lower()


def test_graphiti_memory_service_requires_provider_configuration() -> None:
    settings = _settings()

    service = GraphitiMemoryService(settings=settings, backend=_InMemoryGraphitiBackend())

    service.initialize_indices()

    with pytest.raises(ValueError) as exc_info:
        GraphitiMemoryService(settings=settings).initialize_indices()

    message = str(exc_info.value)
    assert "provider" in message.lower()
    assert "OPENAI_API_KEY" in message


def test_graphiti_memory_service_uses_live_backend_and_surfaces_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    service = GraphitiMemoryService(settings=settings)

    service.initialize_indices()
    with pytest.raises(Exception) as exc_info:
        service.store_episode(
            MemoryEpisode(
                thread_id="thread-live",
                actor="user",
                content="My preferred deployment target is Kubernetes on Neo4j-backed infrastructure.",
            )
        )

    assert "api key" in str(exc_info.value).lower()


def test_graphiti_memory_service_allows_injected_backend_without_provider_config() -> None:
    settings = _settings()
    backend = _InMemoryGraphitiBackend()

    service = GraphitiMemoryService(settings=settings, backend=backend)

    service.initialize_indices()
    service.store_episode(
        MemoryEpisode(
            thread_id="thread-456",
            actor="user",
            content="I prefer Neo4j for graph-backed agent memory.",
        )
    )

    results = service.search_memory("Neo4j graph memory", thread_id="thread-456", limit=1)

    assert backend.initialized is True
    assert len(results) == 1


def test_graphiti_memory_service_stores_and_returns_relevant_memory_when_backend_is_available() -> None:
    settings = _settings()
    service = GraphitiMemoryService(
        settings=settings,
        backend=_InMemoryGraphitiBackend(),
        provider_api_key="test-key",
    )

    service.initialize_indices()
    service.store_episode(
        MemoryEpisode(
            thread_id="thread-123",
            actor="user",
            content="My favorite deployment target is Kubernetes.",
        )
    )
    service.store_episode(
        MemoryEpisode(
            thread_id="thread-123",
            actor="assistant",
            content="I will remember your preferred deployment target.",
        )
    )

    results = service.search_memory("preferred deployment target", thread_id="thread-123", limit=2)

    assert len(results) == 2
    assert results[0].thread_id == "thread-123"
    assert "deployment target" in results[0].content.lower()
    assert results[0].score >= results[1].score


def test_runtime_memory_selection_defaults_to_live_graphiti(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed: dict[str, object] = {}

    def fake_initialize(self) -> None:
        observed["backend"] = self._backend
        self._initialized = True

    monkeypatch.setattr(GraphitiMemoryService, "initialize_indices", fake_initialize)

    ingest_service, workflow_service = build_runtime_services(settings)

    assert observed["backend"] is None
    workflow_service.close()


def test_runtime_memory_selection_uses_injected_backend_for_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed: dict[str, object] = {}

    def fake_initialize(self) -> None:
        observed["backend"] = self._backend
        self._initialized = True

    monkeypatch.setattr(GraphitiMemoryService, "initialize_indices", fake_initialize)
    backend = _InMemoryGraphitiBackend()

    ingest_service, workflow_service = build_runtime_services(
        settings,
        memory_backend=backend,
    )

    assert observed["backend"] is backend
    workflow_service.close()


def test_live_graphiti_backend_uses_basic_search_signature() -> None:
    search_calls: list[dict[str, object]] = []

    class _FakeClient:
        async def build_indices_and_constraints(self) -> None:
            return None

        async def add_episode(self, **kwargs) -> None:
            return None

        async def search(self, query: str, **kwargs):
            search_calls.append({"query": query, **kwargs})
            return [
                SimpleNamespace(
                    fact="Remembered preference",
                    source="user",
                    fact_embedding_similarity=0.9,
                )
            ]

        async def close(self) -> None:
            return None

    service = GraphitiMemoryService(
        settings=_settings(),
        provider_api_key="test-key",
    )
    service._backend = service._backend = __import__(
        "base_agent_system.memory.graphiti_service",
        fromlist=["_LiveGraphitiBackend"],
    )._LiveGraphitiBackend(
        settings=_settings(),
        provider_api_key="test-key",
        graphiti_class=lambda **kwargs: None,
        episode_type="message",
        search_recipe=object(),
    )
    service._backend._client = _FakeClient()
    service._initialized = True

    results = service.search_memory("preferred deployment target", thread_id="thread-123", limit=2)

    assert len(results) == 1
    assert search_calls == [
        {
            "query": "preferred deployment target",
            "group_ids": ["thread-123"],
            "num_results": 2,
        }
    ]


class _InMemoryGraphitiBackend:
    def __init__(self) -> None:
        self.initialized = False
        self.episodes: list[MemoryEpisode] = []

    def initialize_indices(self) -> None:
        self.initialized = True

    def store_episode(self, episode: MemoryEpisode) -> None:
        if not self.initialized:
            raise AssertionError("backend must be initialized before storing episodes")
        self.episodes.append(episode)

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int,
    ) -> list[dict[str, object]]:
        if not self.initialized:
            raise AssertionError("backend must be initialized before searching")

        query_terms = {term for term in query.lower().split() if term}
        matches = []
        for episode in self.episodes:
            if episode.thread_id != thread_id:
                continue
            episode_terms = set(episode.content.lower().split())
            score = float(len(query_terms & episode_terms))
            if score <= 0:
                continue
            matches.append(
                {
                    "thread_id": episode.thread_id,
                    "actor": episode.actor,
                    "content": episode.content,
                    "score": score,
                }
            )

        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:limit]
