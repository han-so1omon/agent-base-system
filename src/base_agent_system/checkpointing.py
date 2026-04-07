"""Boundary for optional Postgres-backed LangGraph checkpointing."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable


SaverFactory = Callable[[str], AbstractContextManager[Any]]


@dataclass
class PostgresCheckpointerHolder:
    _context_manager: AbstractContextManager[Any]
    _saver: Any | None = None

    def open(self) -> Any:
        if self._saver is None:
            saver = self._context_manager.__enter__()
            saver.setup()
            self._saver = saver
        return self._saver

    def close(self) -> None:
        if self._saver is None:
            return
        self._context_manager.__exit__(None, None, None)
        self._saver = None


def build_postgres_checkpointer(
    postgres_uri: str,
    *,
    saver_factory: SaverFactory | None = None,
) -> PostgresCheckpointerHolder:
    if saver_factory is None:
        saver_factory = _default_saver_factory()
    return PostgresCheckpointerHolder(saver_factory(postgres_uri))


def _default_saver_factory() -> SaverFactory:
    try:
        module = import_module("langgraph.checkpoint.postgres")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "LangGraph Postgres checkpointing requires the optional langgraph and "
            "langgraph-checkpoint-postgres dependencies."
        ) from exc

    saver_class = module.PostgresSaver
    return saver_class.from_conn_string
