"""Workflow graph construction for the base agent system."""

from __future__ import annotations

from importlib import import_module
import os
from typing import Any, Callable, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState

from base_agent_system.config import Settings
from base_agent_system.workflow.agent_tools import build_search_docs_tool, build_search_memory_tool
from base_agent_system.workflow.nodes import (
    persist_memory_node,
    retrieve_docs_node,
    retrieve_memory_node,
    synthesize_answer_node,
    workflow_hook_node,
)
from base_agent_system.workflow.state import WorkflowHooks, WorkflowState


class AgentWorkflowState(AgentState, total=False):
    thread_id: str


class AgentWorkflowApp:
    def __init__(self, app: Any, *, tool_context: dict[str, Callable[[list[Any]], None]]) -> None:
        self._app = app
        self._tool_context = tool_context

    def invoke(self, payload: dict[str, Any], **invoke_kwargs: Any) -> dict[str, Any]:
        thread_id = str(payload.get("thread_id", ""))
        messages = list(payload.get("messages", []))
        debug = {"document_hits": 0, "memory_hits": 0, "tool_calls": 0}
        citations: list[dict[str, str]] = []

        def record_docs(results: list[Any]) -> None:
            debug["document_hits"] = len(results)
            debug["tool_calls"] += 1
            citations.clear()
            citations.extend(_build_citations(results))

        def record_memory(results: list[Any]) -> None:
            debug["memory_hits"] = len(results)
            debug["tool_calls"] += 1

        self._tool_context["docs_result_handler"] = record_docs
        self._tool_context["memory_result_handler"] = record_memory
        result = self._app.invoke(
            {"messages": messages, "thread_id": thread_id},
            **invoke_kwargs,
        )
        return {
            "thread_id": thread_id,
            "answer": _extract_answer(result.get("messages", [])),
            "citations": citations,
            "debug": debug,
        }


def build_workflow(
    *,
    settings: Settings,
    retrieval_service: Any,
    memory_service: Any,
    checkpointer: object | None = None,
    state_graph_factory: object | None = None,
    workflow_hooks: object | None = None,
) -> Any:
    if state_graph_factory is not None or workflow_hooks is not None or _should_use_synthetic_workflow(settings):
        return _build_synthetic_workflow(
            settings=settings,
            retrieval_service=retrieval_service,
            memory_service=memory_service,
            checkpointer=checkpointer,
            state_graph_factory=state_graph_factory,
            workflow_hooks=workflow_hooks,
        )

    tool_context: dict[str, Callable[[list[Any]], None]] = {
        "docs_result_handler": lambda results: None,
        "memory_result_handler": lambda results: None,
    }
    tools = [
        build_search_docs_tool(
            retrieval_service,
            on_result=lambda results: tool_context["docs_result_handler"](results),
        ),
        build_search_memory_tool(
            memory_service,
            on_result=lambda results: tool_context["memory_result_handler"](results),
        ),
    ]
    app = create_react_agent(
        model=_build_model(settings),
        tools=tools,
        checkpointer=checkpointer,
        state_schema=AgentWorkflowState,
        prompt=(
            "You are the backend chat agent. Answer conversationally and use tools when"
            " retrieval or thread memory would improve grounding. If retrieved documents"
            " contain relevant context, answer using that context instead of asking a"
            " clarifying question. The current thread id is available in state as"
            " thread_id."
        ),
    )
    return AgentWorkflowApp(app, tool_context=tool_context)


def _build_model(settings: Settings) -> ChatOpenAI:
    api_key = _resolve_openai_api_key(settings) or "missing-api-key"
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=api_key,
    )


def _build_citations(results: list[Any]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for item in results:
        citation = getattr(item, "citation", None)
        if citation is None:
            continue
        citations.append(
            {
                "source": str(getattr(citation, "path", "")),
                "snippet": str(getattr(citation, "snippet", "")),
            }
        )
    return citations


def _extract_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
    return ""


def _build_synthetic_workflow(
    *,
    settings: Settings,
    retrieval_service: Any,
    memory_service: Any,
    checkpointer: object | None,
    state_graph_factory: Callable[[type[Any]], Any] | None,
    workflow_hooks: WorkflowHooks | None,
) -> Any:
    del settings
    graph, start_node, end_node = _build_state_graph(state_graph_factory=state_graph_factory)
    hooks = _normalize_workflow_hooks(workflow_hooks)
    graph.add_node("before_retrieval", workflow_hook_node(hooks["before_retrieval"]))
    graph.add_node("retrieve_docs", retrieve_docs_node(retrieval_service))
    graph.add_node("retrieve_memory", retrieve_memory_node(memory_service))
    graph.add_node("after_retrieval", workflow_hook_node(hooks["after_retrieval"]))
    graph.add_node(
        "before_answer_synthesis",
        workflow_hook_node(hooks["before_answer_synthesis"]),
    )
    graph.add_node("synthesize_answer", synthesize_answer_node())
    graph.add_node(
        "after_answer_synthesis",
        workflow_hook_node(hooks["after_answer_synthesis"]),
    )
    graph.add_node("persist_memory", persist_memory_node(memory_service))
    graph.add_edge(start_node, "before_retrieval")
    graph.add_edge("before_retrieval", "retrieve_docs")
    graph.add_edge("retrieve_docs", "retrieve_memory")
    graph.add_edge("retrieve_memory", "after_retrieval")
    graph.add_edge("after_retrieval", "before_answer_synthesis")
    graph.add_edge("before_answer_synthesis", "synthesize_answer")
    graph.add_edge("synthesize_answer", "after_answer_synthesis")
    graph.add_edge("after_answer_synthesis", "persist_memory")
    graph.add_edge("persist_memory", end_node)
    return graph.compile(checkpointer=checkpointer)


def _build_state_graph(
    *,
    state_graph_factory: Callable[[type[Any]], Any] | None,
) -> tuple[Any, object, object]:
    if state_graph_factory is not None:
        return state_graph_factory(WorkflowState), "START", "END"

    try:
        state_module = import_module("langgraph.graph")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "LangGraph workflow support requires the optional langgraph dependency."
        ) from exc

    return state_module.StateGraph(WorkflowState), state_module.START, state_module.END


def _normalize_workflow_hooks(workflow_hooks: WorkflowHooks | None) -> dict[str, tuple[Any, ...]]:
    hooks = workflow_hooks or {}
    return {
        "before_retrieval": tuple(hooks.get("before_retrieval", ())),
        "after_retrieval": tuple(hooks.get("after_retrieval", ())),
        "before_answer_synthesis": tuple(hooks.get("before_answer_synthesis", ())),
        "after_answer_synthesis": tuple(hooks.get("after_answer_synthesis", ())),
    }


def _resolve_openai_api_key(settings: Settings) -> str:
    return os.getenv(settings.openai_api_key_name, "")


def _should_use_synthetic_workflow(settings: Settings) -> bool:
    api_key = _resolve_openai_api_key(settings).strip()
    return not api_key or (settings.app_env == "test" and api_key.startswith("test"))
