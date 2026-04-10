from __future__ import annotations

from types import SimpleNamespace

import pytest

from base_agent_system.config import Settings
from base_agent_system.interactions.repository import InMemoryInteractionRepository
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        app_env="test",
    )


@pytest.mark.asyncio
async def test_workflow_service_arun_persists_interaction_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.runtime_services import WorkflowService

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    backend = _InMemoryGraphitiBackend()
    memory_service = GraphitiMemoryService(settings=_settings(), backend=backend, provider_api_key="test-key")
    memory_service.initialize_indices()
    interaction_repository = InMemoryInteractionRepository()

    workflow_service = WorkflowService(
        settings=_settings(),
        retrieval_service=SimpleNamespace(),
        memory_service=memory_service,
        temp_dir=SimpleNamespace(cleanup=lambda: None),
        interaction_repository=interaction_repository,
        workflow_builder=lambda **kwargs: _AsyncWorkflowStub(),
    )

    result = await workflow_service.arun(
        thread_id="thread-async-1",
        messages=[{"role": "user", "content": "Remember Kubernetes as my preferred deployment target."}],
    )

    assert result["answer"] == "I will remember Kubernetes."
    page = interaction_repository.list_thread_interactions(thread_id="thread-async-1", limit=20)
    assert [item.kind for item in page.items] == ["user", "agent_run"]
    assert page.items[-1].latest_display_event is not None
    assert page.items[-1].latest_display_event.content == "I will remember Kubernetes."


class _AsyncWorkflowStub:
    async def ainvoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
        del payload, kwargs
        return {
            "thread_id": "thread-async-1",
            "answer": "I will remember Kubernetes.",
            "citations": [],
            "debug": {"document_hits": 0, "memory_hits": 0},
            "interaction": {
                "used_tools": True,
                "tool_call_count": 1,
                "tools_used": ["search_memory"],
                "artifacts": [
                    {
                        "artifact_id": "artifact-123",
                        "storage_backend": "local",
                        "storage_uri": "file:///tmp/artifact.txt",
                        "media_type": "text/plain",
                        "logical_role": "supporting_note",
                        "checksum": "abc123",
                    }
                ],
                "steps": [{"type": "tool_call", "tool": "search_memory"}],
                "intermediate_reasoning": {"kind": "chain_of_thought", "content": "internal"},
            },
        }


@pytest.mark.asyncio
async def test_workflow_service_arun_records_branch_trace_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.runtime_services import WorkflowService

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    backend = _InMemoryGraphitiBackend()
    memory_service = GraphitiMemoryService(settings=_settings(), backend=backend, provider_api_key="test-key")
    memory_service.initialize_indices()

    interaction_repository = InMemoryInteractionRepository()
    parent = interaction_repository.create_interaction(thread_id="thread-async-2", kind="agent_run", status="running")
    child = interaction_repository.create_interaction(
        thread_id="thread-async-2",
        parent_interaction_id=parent.id,
        kind="deep_agent",
        status="queued",
    )
    observability = _RecordingObservabilityService()
    workflow_service = WorkflowService(
        settings=_settings(),
        retrieval_service=SimpleNamespace(),
        memory_service=memory_service,
        temp_dir=SimpleNamespace(cleanup=lambda: None),
        interaction_repository=interaction_repository,
        workflow_builder=lambda **kwargs: _AsyncWorkflowStub(),
        observability_service=observability,
    )

    await workflow_service.arun(
        thread_id="thread-async-2",
        interaction_id=child.id,
        parent_interaction_id=parent.id,
        messages=[{"role": "user", "content": "Remember Kubernetes as my preferred deployment target."}],
    )

    assert observability.branch_traces == [
        {
            "name": "interaction_branch",
            "metadata": {
                "thread_id": "thread-async-2",
                "interaction_id": child.id,
                "parent_interaction_id": parent.id,
                "branch_kind": "child",
                "message_count": 1,
                "user_message_count": 1,
                "tool_call_count": 1,
                "tools_used": ["search_memory"],
                "citation_count": 0,
                "artifact_count": 1,
                "document_hits": 0,
                "memory_hits": 0,
                "status": "completed",
            },
        }
    ]


@pytest.mark.asyncio
async def test_workflow_service_arun_records_failed_branch_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.runtime_services import WorkflowService

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    backend = _InMemoryGraphitiBackend()
    memory_service = GraphitiMemoryService(settings=_settings(), backend=backend, provider_api_key="test-key")
    memory_service.initialize_indices()

    observability = _RecordingObservabilityService()
    workflow_service = WorkflowService(
        settings=_settings(),
        retrieval_service=SimpleNamespace(),
        memory_service=memory_service,
        temp_dir=SimpleNamespace(cleanup=lambda: None),
        interaction_repository=InMemoryInteractionRepository(),
        workflow_builder=lambda **kwargs: _FailingWorkflowStub(),
        observability_service=observability,
    )

    with pytest.raises(RuntimeError, match="workflow exploded"):
        await workflow_service.arun(
            thread_id="thread-async-3",
            interaction_id="interaction-789",
            messages=[{"role": "user", "content": "Do something risky"}],
        )

    assert observability.branch_traces == [
        {
            "name": "interaction_branch",
            "metadata": {
                "thread_id": "thread-async-3",
                "interaction_id": "interaction-789",
                "parent_interaction_id": None,
                "branch_kind": "root",
                "message_count": 1,
                "user_message_count": 1,
                "status": "failed",
                "error_type": "RuntimeError",
            },
        }
    ]


class _FailingWorkflowStub:
    async def ainvoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
        del payload, kwargs
        raise RuntimeError("workflow exploded")


class _RecordingObservabilityService:
    def __init__(self) -> None:
        self.branch_traces: list[dict[str, object]] = []

    class _TraceContext:
        def __init__(self, owner: "_RecordingObservabilityService", name: str, metadata: dict[str, object]) -> None:
            self._owner = owner
            self._name = name
            self._metadata = metadata

        def __enter__(self) -> SimpleNamespace:
            return SimpleNamespace(name=self._name, metadata=self._metadata)

        def __exit__(self, exc_type, exc, tb) -> None:
            self._owner.branch_traces.append({"name": self._name, "metadata": dict(self._metadata)})

    def start_branch_trace(self, *, name: str, metadata: dict[str, object]) -> "_RecordingObservabilityService._TraceContext":
        return self._TraceContext(self, name, metadata)

    class _SpanContext:
        def __enter__(self) -> SimpleNamespace:
            return SimpleNamespace(name="span", metadata={})

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def start_span(self, trace: object, *, name: str, metadata: dict[str, object]) -> "_RecordingObservabilityService._SpanContext":
        del trace, name, metadata
        return self._SpanContext()
