"""Schedule domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Schedule:
    id: str
    thread_id: str
    prompt: str
    cadence: str
    enabled: bool
    next_run_at: str
    last_run_at: str | None = None
    metadata: dict[str, object] | None = None
