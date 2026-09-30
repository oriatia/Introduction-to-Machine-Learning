"""arq worker entry point: `arq hazar_worker.main.WorkerSettings`.

Jobs land here as the sprints add them: document extraction (Sprint 4), agents and scheduled
automations (Sprint 7). Every job must be idempotent and must never log PII.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from arq.connections import RedisSettings

from hazar_api.config import get_settings
from hazar_tax_engine import ENGINE_VERSION

logger = logging.getLogger(__name__)


async def healthcheck(ctx: dict[str, Any]) -> dict[str, str]:
    """Round-trip job used by smoke tests to prove the queue and worker are wired up."""
    return {"status": "ok", "engine_version": ENGINE_VERSION, "job_id": str(ctx.get("job_id", ""))}


async def startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = get_settings()
    logger.info("worker started (env=%s)", ctx["settings"].env)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [healthcheck]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    job_timeout = 300
