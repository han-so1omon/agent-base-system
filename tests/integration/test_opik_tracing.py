from __future__ import annotations

from types import SimpleNamespace

import pytest

from base_agent_system.config import Settings


def _settings(*, enabled: bool) -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        app_env="test",
        opik_enabled=enabled,
        opik_project_name="base-agent-system-tests",
        opik_workspace="team-workspace",
        opik_url="https://opik.example.com",
    )


def test_create_observability_service_returns_noop_when_opik_disabled() -> None:
    from base_agent_system.observability.opik import NoopObservabilityService, create_observability_service

    service = create_observability_service(_settings(enabled=False))

    assert isinstance(service, NoopObservabilityService)
    with service.start_branch_trace(name="branch", metadata={"thread_id": "thread-123"}) as trace:
        assert trace.metadata == {"thread_id": "thread-123"}
        with service.start_span(trace, name="retrieve_docs", metadata={"count": 3}) as span:
            assert span.name == "retrieve_docs"


def test_create_observability_service_bootstraps_enabled_opik_client() -> None:
    from base_agent_system.observability.opik import OpikObservabilityService, create_observability_service

    client_calls: list[dict[str, object]] = []

    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:
            client_calls.append(kwargs)

    fake_module = SimpleNamespace(Opik=_FakeClient)

    service = create_observability_service(_settings(enabled=True), opik_module=fake_module)

    assert isinstance(service, OpikObservabilityService)
    assert client_calls == [
        {
            "project_name": "base-agent-system-tests",
            "workspace": "team-workspace",
            "url": "https://opik.example.com",
            "use_local": False,
            "api_key": "",
        }
    ]


def test_opik_observability_service_records_nested_spans() -> None:
    from base_agent_system.observability.opik import OpikObservabilityService

    events: list[tuple[str, str, dict[str, object]]] = []

    class _FakeSpan:
        def __init__(self, kind: str, name: str, metadata: dict[str, object]) -> None:
            self.kind = kind
            self.name = name
            self.metadata = metadata

        def __enter__(self) -> "_FakeSpan":
            events.append(("enter", self.name, self.metadata))
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            status = "error" if exc_type is not None else "ok"
            events.append(("exit", self.name, {"status": status}))

    class _FakeClient:
        def trace(self, *, name: str, metadata: dict[str, object]) -> _FakeSpan:
            return _FakeSpan("trace", name, metadata)

        def span(self, *, name: str, metadata: dict[str, object], parent: object) -> _FakeSpan:
            assert parent is not None
            return _FakeSpan("span", name, metadata)

    service = OpikObservabilityService(client=_FakeClient())

    with service.start_branch_trace(
        name="interaction_branch",
        metadata={
            "thread_id": "thread-123",
            "interaction_id": "interaction-456",
            "parent_interaction_id": "interaction-111",
        },
    ) as trace:
        with service.start_span(trace, name="retrieve_docs", metadata={"document_hits": 2}):
            pass

    assert events == [
        (
            "enter",
            "interaction_branch",
            {
                "thread_id": "thread-123",
                "interaction_id": "interaction-456",
                "parent_interaction_id": "interaction-111",
            },
        ),
        ("enter", "retrieve_docs", {"document_hits": 2}),
        ("exit", "retrieve_docs", {"status": "ok"}),
        ("exit", "interaction_branch", {"status": "ok"}),
    ]
