"""ARQ worker configuration."""

from __future__ import annotations

from base_agent_system.workers.tasks import run_interaction_branch
from base_agent_system.config import load_settings


class WorkerSettings:
    functions = [run_interaction_branch]
    redis_settings = None


def build_worker_settings() -> type[WorkerSettings]:
    settings = load_settings()

    class ConfiguredWorkerSettings(WorkerSettings):
        redis_settings = settings.arq_redis_uri
        queue_name = settings.arq_queue_name

    return ConfiguredWorkerSettings
