"""arq worker entry point: `arq hazar_worker.main.WorkerSettings`.

Every job must be idempotent and must never log PII or document content.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, ClassVar

from arq.connections import RedisSettings

from hazar_api.config import get_settings
from hazar_api.crypto import LocalKeyWrapper
from hazar_api.db import make_engine, make_sessionmaker
from hazar_api.documents import EXTRACT_JOB, run_extraction
from hazar_api.extraction import make_extractor
from hazar_api.storage import S3ObjectStorage
from hazar_api.vault import DocumentVault
from hazar_tax_engine import ENGINE_VERSION

logger = logging.getLogger(__name__)


async def healthcheck(ctx: dict[str, Any]) -> dict[str, str]:
    """Round-trip job used by smoke tests to prove the queue and worker are wired up."""
    return {"status": "ok", "engine_version": ENGINE_VERSION, "job_id": str(ctx.get("job_id", ""))}


async def extract_document(ctx: dict[str, Any], document_id: str) -> str:
    return await run_extraction(ctx["sessionmaker"], ctx["vault"], ctx["extractor"], uuid.UUID(document_id))


extract_document.__name__ = EXTRACT_JOB


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["settings"] = settings
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    storage = S3ObjectStorage(
        settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key.get_secret_value(),
        secret_key=settings.s3_secret_key.get_secret_value(),
        region=settings.s3_region,
    )
    await storage.ensure_bucket()
    ctx["vault"] = DocumentVault(storage, LocalKeyWrapper(settings.master_key), settings.secret_bytes)
    ctx["extractor"] = make_extractor(settings)
    logger.info("worker started (env=%s, extractor=%s)", settings.env, ctx["extractor"].name)


async def shutdown(ctx: dict[str, Any]) -> None:
    if "engine" in ctx:
        await ctx["engine"].dispose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [healthcheck, extract_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    job_timeout = 300
