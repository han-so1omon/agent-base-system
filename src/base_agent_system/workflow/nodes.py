"""Minimal workflow nodes for retrieval, synthesis, and persistence."""

from __future__ import annotations

from typing import Protocol

from base_agent_system.memory.models import MemoryEpisode, MemorySearchResult
from base_agent_system.retrieval.models import RetrievalResult
from base_agent_system.workflow.state import WorkflowHook, WorkflowState


class RetrievalService(Protocol):
    def query(self, text: str, *, top_k: int, context_policy: dict[str, object] | None = None) -> list[RetrievalResult]: ...


class MemoryService(Protocol):
    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int = 5,
        context_policy: dict[str, object] | None = None,
    ) -> list[MemorySearchResult]: ...

    def store_episode(self, episode: MemoryEpisode) -> None: ...


def retrieve_docs_node(retrieval_service: RetrievalService):
    def retrieve_docs(state: WorkflowState) -> WorkflowState:
        try:
            results = retrieval_service.query(
                state["query"],
                top_k=3,
                context_policy=state.get("context_policy"),
            )
        except TypeError:
            results = retrieval_service.query(state["query"], top_k=3)
        return {
            "retrieved_docs": [
                {
                    "text": item.text,
                    "score": item.score,
                    "citation": {
                        "source": item.citation.path,
                        "snippet": item.citation.snippet,
                    },
                }
                for item in results
            ]
        }

    return retrieve_docs


def retrieve_memory_node(memory_service: MemoryService):
    def retrieve_memory(state: WorkflowState) -> WorkflowState:
        try:
            results = memory_service.search_memory(
                state["query"],
                thread_id=state["thread_id"],
                limit=3,
                context_policy=state.get("context_policy"),
            )
        except TypeError:
            results = memory_service.search_memory(
                state["query"],
                thread_id=state["thread_id"],
                limit=3,
            )
        return {
            "retrieved_memory": [
                {
                    "thread_id": item.thread_id,
                    "actor": item.actor,
                    "content": item.content,
                    "score": item.score,
                }
                for item in results
            ]
        }

    return retrieve_memory


def synthesize_answer_node():
    def synthesize_answer(state: WorkflowState) -> WorkflowState:
        docs = state.get("retrieved_docs", [])
        memory = state.get("retrieved_memory", [])
        debug = dict(state.get("debug", {}))
        citations = [item["citation"] for item in docs]
        parts = []
        if docs:
            parts.append(f"Docs: {docs[0]['text']}")
        if memory:
            parts.append(f"Memory: {memory[0]['content']}")
        if not parts:
            parts.append("No supporting context was retrieved.")
        return {
            "answer": " ".join(parts),
            "citations": citations,
            "debug": {
                **debug,
                "document_hits": len(docs),
                "memory_hits": len(memory),
            },
        }

    return synthesize_answer


def persist_memory_node(memory_service: MemoryService):
    def persist_memory(state: WorkflowState) -> WorkflowState:
        memory_service.store_episode(
            MemoryEpisode(
                thread_id=state["thread_id"],
                actor="user",
                content=state["query"],
            )
        )
        memory_service.store_episode(
            MemoryEpisode(
                thread_id=state["thread_id"],
                actor="assistant",
                content=state["answer"],
            )
        )
        return {}

    return persist_memory


def workflow_hook_node(hooks: tuple[WorkflowHook, ...]):
    def run_hooks(state: WorkflowState) -> WorkflowState:
        updates: WorkflowState = {}
        current_state = dict(state)
        for hook in hooks:
            hook_update = hook(current_state)
            current_state.update(hook_update)
            updates.update(hook_update)
        return updates

    return run_hooks
