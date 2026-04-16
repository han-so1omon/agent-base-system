"""Opik observability adapters."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Protocol

import opik
from opik import opik_context

logger = logging.getLogger(__name__)

class TraceContext(Protocol):
    def update_metadata(self, metadata: dict[str, Any]) -> None: ...

class SpanContext(Protocol):
    def update_metadata(self, metadata: dict[str, Any]) -> None: ...

class ObservabilityService(Protocol):
    @contextmanager
    def start_branch_trace(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        parent_interaction_id: str | None = None,
        name: str = "interaction_branch",
    ) -> Generator[TraceContext, None, None]: ...

    @contextmanager
    def start_span(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanContext, None, None]: ...

    def flush(self) -> None: ...


class NoopObservabilityService:
    @contextmanager
    def start_branch_trace(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        parent_interaction_id: str | None = None,
        name: str = "interaction_branch",
    ) -> Generator[TraceContext, None, None]:
        yield _NoopContext()

    @contextmanager
    def start_span(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanContext, None, None]:
        yield _NoopContext()

    def flush(self) -> None:
        pass


class _NoopContext:
    def update_metadata(self, metadata: dict[str, Any]) -> None:
        pass


class OpikObservabilityService:
    def __init__(
        self,
        *,
        project_name: str = "base-agent-system",
        workspace: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        use_local: bool = False,
    ) -> None:
        # Opik SDK handles env vars and local config automatically.
        # Note: Opik client takes host= instead of url=
        self._project_name = project_name
        self._client = opik.Opik(
            project_name=project_name,
            workspace=workspace,
            host=url,
            api_key=api_key,
        )

    @contextmanager
    def start_branch_trace(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        parent_interaction_id: str | None = None,
        name: str = "interaction_branch",
    ) -> Generator[TraceContext, None, None]:
        metadata = {
            "thread_id": thread_id,
            "interaction_id": interaction_id,
            "parent_interaction_id": parent_interaction_id,
        }
        current_trace = opik_context.get_current_trace_data()
        if current_trace is not None:
            opik_context.update_current_trace(metadata=metadata)
            yield _OpikCurrentTraceContext()
            return

        with opik.start_as_current_trace(
            name=name,
            metadata=metadata,
            project_name=self._project_name,
        ) as trace:
            yield _OpikTraceContext(trace)

    @contextmanager
    def start_span(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanContext, None, None]:
        with opik.start_as_current_span(
            name=name,
            metadata=metadata,
            project_name=self._project_name,
        ) as span:
            yield _OpikSpanContext(span)

    def flush(self) -> None:
        opik.flush_tracker()


class _OpikTraceContext:
    def __init__(self, trace: Any) -> None:
        self._trace = trace

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        # Opik Trace objects use 'metadata' attribute directly or 'update_metadata'
        # depending on version. We'll use the public update_metadata if available,
        # otherwise we'll try to set/update the metadata dict.
        if hasattr(self._trace, "update_metadata"):
            self._trace.update_metadata(metadata)
        elif hasattr(self._trace, "metadata"):
            if getattr(self._trace, "metadata") is None:
                setattr(self._trace, "metadata", metadata)
            else:
                getattr(self._trace, "metadata").update(metadata)


class _OpikSpanContext:
    def __init__(self, span: Any) -> None:
        self._span = span

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        if hasattr(self._span, "update_metadata"):
            self._span.update_metadata(metadata)
        elif hasattr(self._span, "update"):
            self._span.update(metadata=metadata)
        elif hasattr(self._span, "metadata"):
            if getattr(self._span, "metadata") is None:
                setattr(self._span, "metadata", metadata)
            else:
                getattr(self._span, "metadata").update(metadata)


class _OpikCurrentTraceContext:
    def update_metadata(self, metadata: dict[str, Any]) -> None:
        opik_context.update_current_trace(metadata=metadata)
