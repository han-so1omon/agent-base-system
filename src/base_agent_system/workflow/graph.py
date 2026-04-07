"""Workflow graph construction for the base agent system."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

from base_agent_system.config import Settings
from base_agent_system.workflow.nodes import (
    MemoryService,
    RetrievalService,
    persist_memory_node,
    retrieve_docs_node,
    retrieve_memory_node,
    synthesize_answer_node,
    workflow_hook_node,
)
from base_agent_system.workflow.state import WorkflowHooks, WorkflowState


StateGraphFactory = Callable[[type[WorkflowState]], Any]


def build_workflow(
    *,
    settings: Settings,
    retrieval_service: RetrievalService,
    memory_service: MemoryService,
    checkpointer: object | None = None,
    state_graph_factory: StateGraphFactory | None = None,
    workflow_hooks: WorkflowHooks | None = None,
) -> Any:
    del settings

    graph, start_node, end_node = _build_state_graph(state_graph_factory)
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


def _build_state_graph(state_graph_factory: StateGraphFactory | None) -> tuple[Any, object, object]:
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
