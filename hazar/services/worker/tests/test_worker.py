from __future__ import annotations

import os

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from hazar_worker.main import WorkerSettings, healthcheck


async def test_healthcheck_job() -> None:
    result = await healthcheck({"job_id": "abc"})
    assert result["status"] == "ok"
    assert result["job_id"] == "abc"


def test_worker_registers_jobs() -> None:
    names = {f.__name__ for f in WorkerSettings.functions}
    assert "healthcheck" in names


@pytest.mark.skipif(not os.environ.get("HAZAR_TEST_REDIS_URL"), reason="HAZAR_TEST_REDIS_URL not set")
async def test_job_round_trip_through_redis() -> None:
    settings = RedisSettings.from_dsn(os.environ["HAZAR_TEST_REDIS_URL"])
    pool = await create_pool(settings)
    try:
        job = await pool.enqueue_job("healthcheck")
        assert job is not None
        worker = Worker(functions=[healthcheck], redis_settings=settings, burst=True, poll_delay=0.01)
        await worker.async_run()
        await worker.close()
        result = await job.result(timeout=5)
        assert result["status"] == "ok"
    finally:
        await pool.aclose()
