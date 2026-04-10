"""Thin Opik integration wrappers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Any, Iterator

from base_agent_system.config import Settings


@dataclass(frozen=True)
class TraceHandle:
    name: str
    metadata: dict[str, object]
    raw: object | None = None


@dataclass(frozen=True)
class SpanHandle:
    name: str
    metadata: dict[str, object]
    raw: object | None = None


class NoopObservabilityService:
    @contextmanager
    def start_branch_trace(self, *, name: str, metadata: dict[str, object]) -> Iterator[TraceHandle]:
        yield TraceHandle(name=name, metadata=metadata)

    @contextmanager
    def start_span(
        self,
        trace: TraceHandle,
        *,
        name: str,
        metadata: dict[str, object],
    ) -> Iterator[SpanHandle]:
        del trace
        yield SpanHandle(name=name, metadata=metadata)

    def flush(self) -> None:
        return None


class OpikObservabilityService:
    def __init__(self, *, client: object) -> None:
        self._client = client

    @contextmanager
    def start_branch_trace(self, *, name: str, metadata: dict[str, object]) -> Iterator[TraceHandle]:
        with self._client.trace(name=name, metadata=metadata) as raw_trace:
            yield TraceHandle(name=name, metadata=metadata, raw=raw_trace)

    @contextmanager
    def start_span(
        self,
        trace: TraceHandle,
        *,
        name: str,
        metadata: dict[str, object],
    ) -> Iterator[SpanHandle]:
        with self._client.span(name=name, metadata=metadata, parent=trace.raw) as raw_span:
            yield SpanHandle(name=name, metadata=metadata, raw=raw_span)

    def flush(self) -> None:
        flush = getattr(self._client, "flush", None)
        if callable(flush):
            flush()


def create_observability_service(settings: Settings, *, opik_module: object | None = None) -> object:
    if not settings.opik_enabled:
        return NoopObservabilityService()
    module = opik_module or _import_opik_module()
    client = module.Opik(
        project_name=settings.opik_project_name,
        workspace=settings.opik_workspace,
        url=settings.opik_url,
        use_local=settings.opik_use_local,
        api_key=os.getenv(settings.opik_api_key_name, ""),
    )
    return OpikObservabilityService(client=client)


def _import_opik_module() -> Any:
    try:
        import opik
    except ModuleNotFoundError as exc:
        raise RuntimeError("Opik support requires the optional opik dependency.") from exc
    return opik
