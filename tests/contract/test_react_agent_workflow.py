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
