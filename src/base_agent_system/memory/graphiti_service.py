"""Minimal Graphiti memory adapter with explicit config and live backend support."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from importlib import import_module
import os
from threading import Thread
from typing import Any, Protocol

from base_agent_system.config import Settings
from base_agent_system.memory.models import MemoryEpisode, MemorySearchResult


class GraphitiMemoryBackend(Protocol):
    def initialize_indices(self) -> None: ...

    def store_episode(self, episode: MemoryEpisode) -> None: ...

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class GraphitiMemoryService:
    def __init__(
        self,
        *,
        settings: Settings,
        backend: GraphitiMemoryBackend | None = None,
        provider_api_key: str | None = None,
    ) -> None:
        self._settings = settings
        _validate_neo4j_settings(settings)
        self._provider_api_key = provider_api_key
        self._backend = backend
        self._initialized = False

    def initialize_indices(self) -> None:
        if self._backend is None:
            self._backend = _build_graphiti_backend(
                settings=self._settings,
                provider_api_key=self._provider_api_key,
            )
        self._backend.initialize_indices()
        self._initialized = True

    def store_episode(self, episode: MemoryEpisode) -> None:
        self._require_initialized()
        self._backend.store_episode(episode)

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int = 5,
    ) -> list[MemorySearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        self._require_initialized()
        raw_results = self._backend.search_memory(
            query,
            thread_id=thread_id,
            limit=limit,
        )
        return [_coerce_search_result(item) for item in raw_results]

    def _require_initialized(self) -> None:
        if not self._initialized or self._backend is None:
            raise RuntimeError("Graphiti memory service must be initialized before use")

    def close(self) -> None:
        if self._backend is not None and hasattr(self._backend, "close"):
            self._backend.close()
        self._initialized = False


def _validate_neo4j_settings(settings: Settings) -> None:
    missing_fields = []
    if not settings.neo4j_uri.strip():
        missing_fields.append("neo4j_uri")
    if not settings.neo4j_user.strip():
        missing_fields.append("neo4j_user")
    if not settings.neo4j_password.strip():
        missing_fields.append("neo4j_password")
    if not settings.neo4j_database.strip():
        missing_fields.append("neo4j_database")
    if missing_fields:
        raise ValueError(
            "Missing required Neo4j configuration for Graphiti memory: "
            + ", ".join(missing_fields)
        )


def _resolve_provider_api_key(settings: Settings) -> str:
    provider_env_names = [
        settings.openai_api_key_name,
        settings.anthropic_api_key_name,
    ]
    for env_name in provider_env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return value

    raise ValueError(
        "Missing provider configuration for Graphiti memory. Set "
        f"{provider_env_names[0]} or pass provider_api_key explicitly."
    )


def _build_graphiti_backend(
    *,
    settings: Settings,
    provider_api_key: str | None,
) -> GraphitiMemoryBackend:
    provider_api_key = provider_api_key or _resolve_provider_api_key(settings)

    try:
        graphiti_module = import_module("graphiti_core")
        nodes_module = import_module("graphiti_core.nodes")
        recipes_module = import_module("graphiti_core.search.search_config_recipes")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Graphiti memory support requires the optional graphiti-core dependency. "
            "Install graphiti-core to enable the live backend."
        ) from exc

    return _LiveGraphitiBackend(
        settings=settings,
        provider_api_key=provider_api_key,
        graphiti_class=graphiti_module.Graphiti,
        episode_type=nodes_module.EpisodeType.message,
        search_recipe=recipes_module.EDGE_HYBRID_SEARCH_RRF,
    )


class _LiveGraphitiBackend:
    def __init__(
        self,
        *,
        settings: Settings,
        provider_api_key: str,
        graphiti_class: type[Any],
        episode_type: Any,
        search_recipe: Any,
    ) -> None:
        self._graphiti_class = graphiti_class
        self._episode_type = episode_type
        os.environ.setdefault(settings.openai_api_key_name, provider_api_key)
        self._runner = _AsyncRunner()
        self._client = self._runner.run(
            self._create_client(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
            )
        )

    async def _create_client(self, *, uri: str, user: str, password: str) -> Any:
        return self._graphiti_class(uri=uri, user=user, password=password)

    def initialize_indices(self) -> None:
        self._runner.run(self._client.build_indices_and_constraints())

    def store_episode(self, episode: MemoryEpisode) -> None:
        self._runner.run(
            self._client.add_episode(
                name=f"{episode.actor}-{episode.thread_id}",
                episode_body=episode.content,
                source_description="base-agent-system-memory",
                reference_time=datetime.now(timezone.utc),
                source=self._episode_type,
                group_id=episode.thread_id,
            )
        )

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        search_results = self._runner.run(
            self._client.search(
                query,
                group_ids=[thread_id],
                num_results=limit,
            )
        )

        coerced_results: list[dict[str, Any]] = []
        for item in search_results:
            fact = getattr(item, "fact", None) or getattr(item, "name", None) or str(item)
            actor = getattr(item, "source", None) or "memory"
            score = getattr(item, "fact_embedding_similarity", None)
            if score is None:
                score = getattr(item, "rank", None)
            coerced_results.append(
                {
                    "thread_id": thread_id,
                    "actor": str(actor),
                    "content": str(fact),
                    "score": float(score or 0.0),
                }
            )
        return coerced_results

    def close(self) -> None:
        self._runner.run(self._client.close())
        self._runner.close()


class _AsyncRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coroutine: Any) -> Any:
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=1)


def _coerce_search_result(item: dict[str, Any]) -> MemorySearchResult:
    return MemorySearchResult(
        thread_id=str(item["thread_id"]),
        actor=str(item["actor"]),
        content=str(item["content"]),
        score=float(item["score"]),
    )
