import pytest
from unittest.mock import MagicMock, patch
from base_agent_system.observability import NoopObservabilityService, OpikObservabilityService

def test_noop_observability_service_returns_safe_context() -> None:
    service = NoopObservabilityService()
    with service.start_branch_trace(thread_id="t1", interaction_id="i1") as trace:
        assert trace is not None
        trace.update_metadata({"foo": "bar"})

def test_opik_observability_service_bootstraps_when_enabled() -> None:
    with patch("opik.Opik") as mock_opik:
        service = OpikObservabilityService(
            project_name="test-project",
            api_key="test-key"
        )
        assert mock_opik.called
        # Check call arguments
        args, kwargs = mock_opik.call_args
        assert kwargs["project_name"] == "test-project"
        assert kwargs["api_key"] == "test-key"

def test_opik_observability_service_starts_trace() -> None:
    mock_trace = MagicMock()
    mock_trace_context = MagicMock()
    mock_trace_context.__enter__.return_value = mock_trace

    with patch("opik.Opik"), patch("opik.start_as_current_trace", return_value=mock_trace_context) as mock_start_trace:
        service = OpikObservabilityService()
        
        with service.start_branch_trace(thread_id="t1", interaction_id="i1") as trace:
            assert mock_start_trace.called
            _, kwargs = mock_start_trace.call_args
            assert kwargs["metadata"]["thread_id"] == "t1"
            assert kwargs["metadata"]["interaction_id"] == "i1"
            
            trace.update_metadata({"status": "ok"})
            assert mock_trace.update_metadata.called
            assert mock_trace.update_metadata.call_args[0][0] == {"status": "ok"}


def test_opik_observability_service_reuses_current_trace_when_present() -> None:
    existing_trace = MagicMock()

    with (
        patch("opik.Opik"),
        patch("opik.opik_context.get_current_trace_data", return_value=existing_trace),
        patch("opik.opik_context.update_current_trace") as mock_update_current_trace,
        patch("opik.start_as_current_trace") as mock_start_trace,
    ):
        service = OpikObservabilityService(project_name="test-project")

        with service.start_branch_trace(thread_id="t1", interaction_id="i1") as trace:
            trace.update_metadata({"status": "ok"})

    mock_start_trace.assert_not_called()
    assert mock_update_current_trace.call_args_list[0].kwargs == {
        "metadata": {
            "thread_id": "t1",
            "interaction_id": "i1",
            "parent_interaction_id": None,
        }
    }
    assert mock_update_current_trace.call_args_list[1].kwargs == {
        "metadata": {"status": "ok"}
    }


def test_opik_observability_service_starts_span() -> None:
    mock_span = MagicMock()
    mock_span_context = MagicMock()
    mock_span_context.__enter__.return_value = mock_span

    with patch("opik.Opik"), patch("opik.start_as_current_span", return_value=mock_span_context) as mock_start_span:
        service = OpikObservabilityService(project_name="test-project")

        with service.start_span(name="POST /interact", metadata={"thread_id": "t1"}) as span:
            span.update_metadata({"status": "ok"})

        assert mock_start_span.called
        _, kwargs = mock_start_span.call_args
        assert kwargs["name"] == "POST /interact"
        assert kwargs["metadata"] == {"thread_id": "t1"}
        assert kwargs["project_name"] == "test-project"
        mock_span.update_metadata.assert_called_once_with({"status": "ok"})


def test_opik_observability_service_flushes_global_tracker() -> None:
    with patch("opik.Opik"), patch("opik.flush_tracker") as mock_flush_tracker:
        service = OpikObservabilityService(project_name="test-project")

        service.flush()

        mock_flush_tracker.assert_called_once_with()

def test_workflow_service_arun_is_traced() -> None:
    from base_agent_system.runtime_services import WorkflowService
    from base_agent_system.config import Settings
    
    mock_obs = MagicMock()
    mock_obs.start_branch_trace.return_value.__enter__.return_value = MagicMock()
    
    # Minimal constructor requirements
    mock_retrieval = MagicMock()
    mock_memory = MagicMock()
    # Mock astore_episode to be async
    from unittest.mock import AsyncMock
    mock_memory.astore_episode = AsyncMock()
    
    mock_repo = MagicMock()
    
    def mock_workflow_builder(**kwargs):
        mock_app = MagicMock()
        # Setup as async mock
        mock_app.ainvoke = AsyncMock(return_value={
            "thread_id": "t1",
            "answer": "ans",
            "citations": [],
            "debug": {"tool_calls": 0},
            "interaction": {"used_tools": False, "tool_call_count": 0}
        })
        return mock_app

    # Patch build_postgres_checkpointer to avoid real connection attempt
    with patch("base_agent_system.runtime_services.build_postgres_checkpointer") as mock_build_cp:
        settings = Settings(neo4j_uri="bolt://localhost:7687", postgres_uri="postgresql://localhost:5432/db")
        service = WorkflowService(
            settings=settings,
            retrieval_service=mock_retrieval,
            memory_service=mock_memory,
            temp_dir=MagicMock(),
            interaction_repository=mock_repo,
            workflow_builder=mock_workflow_builder,
            observability_service=mock_obs,
        )
    
    import asyncio
    asyncio.run(service.arun(thread_id="t1", interaction_id="i1"))
    
    assert mock_obs.start_branch_trace.called
    args, kwargs = mock_obs.start_branch_trace.call_args
    assert kwargs["thread_id"] == "t1"
    assert kwargs["interaction_id"] == "i1"


def test_workflow_service_arun_wraps_work_in_spans() -> None:
    from base_agent_system.runtime_services import WorkflowService
    from base_agent_system.config import Settings
    from unittest.mock import AsyncMock

    mock_trace = MagicMock()
    mock_branch_context = MagicMock()
    mock_branch_context.__enter__.return_value = mock_trace

    mock_span_context = MagicMock()
    mock_span_context.__enter__.return_value = MagicMock()

    mock_obs = MagicMock()
    mock_obs.start_branch_trace.return_value = mock_branch_context
    mock_obs.start_span.return_value = mock_span_context

    mock_retrieval = MagicMock()
    mock_memory = MagicMock()
    mock_memory.astore_episode = AsyncMock()
    mock_repo = MagicMock()

    def mock_workflow_builder(**kwargs):
        mock_app = MagicMock()
        mock_app.ainvoke = AsyncMock(return_value={
            "thread_id": "t1",
            "answer": "ans",
            "citations": [],
            "debug": {"tool_calls": 1},
            "interaction": {"used_tools": True, "tool_call_count": 1, "tools_used": ["firecrawl_search"], "steps": []},
        })
        return mock_app

    with patch("base_agent_system.runtime_services.build_postgres_checkpointer"):
        settings = Settings(neo4j_uri="bolt://localhost:7687", postgres_uri="postgresql://localhost:5432/db")
        service = WorkflowService(
            settings=settings,
            retrieval_service=mock_retrieval,
            memory_service=mock_memory,
            temp_dir=MagicMock(),
            interaction_repository=mock_repo,
            workflow_builder=mock_workflow_builder,
            observability_service=mock_obs,
        )

    import asyncio
    asyncio.run(service.arun(thread_id="t1", interaction_id="i1", query="hello"))

    span_names = [call.kwargs["name"] for call in mock_obs.start_span.call_args_list]
    assert "workflow_invoke" in span_names
    assert "persist_conversation_turns" in span_names
    assert "persist_interactions" in span_names


def test_workflow_service_arun_flushes_observability() -> None:
    from base_agent_system.runtime_services import WorkflowService
    from base_agent_system.config import Settings
    from unittest.mock import AsyncMock

    mock_obs = MagicMock()
    mock_obs.start_branch_trace.return_value.__enter__.return_value = MagicMock()
    mock_obs.start_span.return_value.__enter__.return_value = MagicMock()

    mock_retrieval = MagicMock()
    mock_memory = MagicMock()
    mock_memory.astore_episode = AsyncMock()
    mock_repo = MagicMock()

    def mock_workflow_builder(**kwargs):
        mock_app = MagicMock()
        mock_app.ainvoke = AsyncMock(return_value={
            "thread_id": "t1",
            "answer": "ans",
            "citations": [],
            "debug": {"tool_calls": 0},
            "interaction": {"used_tools": False, "tool_call_count": 0, "tools_used": [], "steps": []},
        })
        return mock_app

    with patch("base_agent_system.runtime_services.build_postgres_checkpointer"):
        settings = Settings(neo4j_uri="bolt://localhost:7687", postgres_uri="postgresql://localhost:5432/db")
        service = WorkflowService(
            settings=settings,
            retrieval_service=mock_retrieval,
            memory_service=mock_memory,
            temp_dir=MagicMock(),
            interaction_repository=mock_repo,
            workflow_builder=mock_workflow_builder,
            observability_service=mock_obs,
        )

    import asyncio
    asyncio.run(service.arun(thread_id="t1", interaction_id="i1", query="hello"))

    mock_obs.flush.assert_called_once_with()


def test_workflow_service_arun_flushes_after_branch_trace_exits() -> None:
    from base_agent_system.runtime_services import WorkflowService
    from base_agent_system.config import Settings
    from unittest.mock import AsyncMock

    events: list[str] = []

    class _BranchTraceContext:
        def __enter__(self) -> MagicMock:
            return MagicMock()

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("trace_exit")

    mock_obs = MagicMock()
    mock_obs.start_branch_trace.return_value = _BranchTraceContext()
    mock_obs.start_span.return_value.__enter__.return_value = MagicMock()
    mock_obs.flush.side_effect = lambda: events.append("flush")

    mock_retrieval = MagicMock()
    mock_memory = MagicMock()
    mock_memory.astore_episode = AsyncMock()
    mock_repo = MagicMock()

    def mock_workflow_builder(**kwargs):
        mock_app = MagicMock()
        mock_app.ainvoke = AsyncMock(return_value={
            "thread_id": "t1",
            "answer": "ans",
            "citations": [],
            "debug": {"tool_calls": 0},
            "interaction": {"used_tools": False, "tool_call_count": 0, "tools_used": [], "steps": []},
        })
        return mock_app

    with patch("base_agent_system.runtime_services.build_postgres_checkpointer"):
        settings = Settings(neo4j_uri="bolt://localhost:7687", postgres_uri="postgresql://localhost:5432/db")
        service = WorkflowService(
            settings=settings,
            retrieval_service=mock_retrieval,
            memory_service=mock_memory,
            temp_dir=MagicMock(),
            interaction_repository=mock_repo,
            workflow_builder=mock_workflow_builder,
            observability_service=mock_obs,
        )

    import asyncio
    asyncio.run(service.arun(thread_id="t1", interaction_id="i1", query="hello"))

    assert events == ["trace_exit", "flush"]
