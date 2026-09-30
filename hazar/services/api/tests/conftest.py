from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hazar_api.db import make_engine

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "HAZAR_TEST_DATABASE_URL", "postgresql+asyncpg://hazar:hazar@localhost:5432/hazar_test"
)
TABLES = ("users", "audit_log")


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


async def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    admin = make_engine(parsed.set(database="postgres").render_as_string(hide_password=False))
    async with admin.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": parsed.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    await admin.dispose()

    engine = make_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    asyncio.run(_ensure_database(TEST_DATABASE_URL))
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = make_engine(database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def sessionmaker(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as conn:
        # TRUNCATE does not fire the row-level append-only trigger on audit_log.
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
