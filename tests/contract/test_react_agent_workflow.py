from __future__ import annotations

from base_agent_system.config import Settings
from base_agent_system.workflow.graph import build_workflow


def test_build_workflow_constructs_react_agent_with_tools_and_checkpointer(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class _FakeApp:
        pass

    def fake_chat_openai(**kwargs):
        captured["model_kwargs"] = kwargs
        return "fake-model"

    def fake_create_react_agent(*, model, tools, checkpointer, state_schema, prompt):
        captured["model"] = model
        captured["tool_names"] = [tool.name for tool in tools]
        captured["checkpointer"] = checkpointer
        captured["state_schema"] = state_schema
        captured["prompt"] = prompt
        return _FakeApp()

    monkeypatch.setattr("base_agent_system.workflow.graph.ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr("base_agent_system.workflow.graph.create_react_agent", fake_create_react_agent)

    settings = Settings(
        neo4j_uri="bolt://localhost:7687",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )
    app = build_workflow(
        settings=settings,
        retrieval_service=_RetrievalServiceStub(),
        memory_service=_MemoryServiceStub(),
        checkpointer="checkpoint-handle",
    )

    assert hasattr(app, "invoke")
    assert captured == {
        "model_kwargs": {
            "model": "gpt-4o-mini",
            "api_key": "test-openai-key",
        },
        "model": "fake-model",
        "tool_names": ["search_docs", "search_memory"],
        "checkpointer": "checkpoint-handle",
        "state_schema": _state_schema(),
        "prompt": (
            "You are the backend chat agent. Answer conversationally and use tools when"
            " retrieval or thread memory would improve grounding. If retrieved documents"
            " contain relevant context, answer using that context instead of asking a"
            " clarifying question. The current thread id is available in state as"
            " thread_id."
        ),
    }


class _RetrievalServiceStub:
    def query(self, text: str, *, top_k: int):
        raise AssertionError("tool should not be executed in builder contract test")


class _MemoryServiceStub:
    def search_memory(self, query: str, *, thread_id: str, limit: int = 5):
        raise AssertionError("tool should not be executed in builder contract test")


def _state_schema():
    from base_agent_system.workflow.graph import AgentWorkflowState

    return AgentWorkflowState


def test_agent_workflow_app_returns_structured_interaction_metadata() -> None:
    class _StubApp:
        def invoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
            del kwargs
            return {
                "messages": [],
                "intermediate_reasoning": {"kind": "chain_of_thought", "content": "internal"},
            }

    from base_agent_system.workflow.graph import AgentWorkflowApp

    app = AgentWorkflowApp(_StubApp(), model=None, tool_context={})

    result = app.invoke(
        {
            "thread_id": "thread-123",
            "messages": [{"role": "user", "content": "What does the seed doc say?"}],
        }
    )

    assert result["interaction"] == {
        "used_tools": False,
        "tool_call_count": 0,
        "tools_used": [],
        "steps": [],
        "intermediate_reasoning": {"kind": "chain_of_thought", "content": "internal"},
    }


def test_agent_workflow_app_returns_spawn_metadata_when_agent_delegates() -> None:
    class _StubApp:
        def invoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
            del payload, kwargs
            return {
                "messages": [],
                "intermediate_reasoning": {"kind": "chain_of_thought", "content": "delegate"},
                "spawn": {
                    "mode": "deep_agent",
                    "label": "Deep Agent",
                    "plan": ["search broadly", "summarize findings"],
                },
            }

    from base_agent_system.workflow.graph import AgentWorkflowApp

    class _ModelStub:
        def bind(self, **kwargs):
            return self

        def invoke(self, messages):
            raise AssertionError("direct model path should not be used for delegation test")

    app = AgentWorkflowApp(_StubApp(), model=_ModelStub(), tool_context={})

    result = app.invoke(
        {
            "thread_id": "thread-123",
            "messages": [{"role": "user", "content": "Use tools to research this system deeply."}],
        }
    )

    assert result["interaction"]["spawn"] == {
        "mode": "deep_agent",
        "label": "Deep Agent",
        "plan": ["search broadly", "summarize findings"],
    }
