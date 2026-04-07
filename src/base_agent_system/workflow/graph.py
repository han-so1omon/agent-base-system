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
)
from base_agent_system.workflow.state import WorkflowState


StateGraphFactory = Callable[[type[WorkflowState]], Any]


def build_workflow(
    *,
    settings: Settings,
    retrieval_service: RetrievalService,
    memory_service: MemoryService,
    checkpointer: object | None = None,
    state_graph_factory: StateGraphFactory | None = None,
) -> Any:
    graph, start_node, end_node = _build_state_graph(state_graph_factory)
    graph.add_node("retrieve_docs", retrieve_docs_node(retrieval_service))
    graph.add_node("retrieve_memory", retrieve_memory_node(memory_service))
    graph.add_node("synthesize_answer", synthesize_answer_node())
    graph.add_node("persist_memory", persist_memory_node(memory_service))
    graph.add_edge(start_node, "retrieve_docs")
    graph.add_edge("retrieve_docs", "retrieve_memory")
    graph.add_edge("retrieve_memory", "synthesize_answer")
    graph.add_edge("synthesize_answer", "persist_memory")
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
