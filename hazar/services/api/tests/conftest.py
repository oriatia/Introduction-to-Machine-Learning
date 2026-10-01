from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import fakeredis
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hazar_api.config import Settings
from hazar_api.db import make_engine
from hazar_api.main import create_app
from hazar_api.storage import InMemoryObjectStorage

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "HAZAR_TEST_DATABASE_URL", "postgresql+asyncpg://hazar:hazar@localhost:5432/hazar_test"
)
# Fixed "today" for API tests: refund window is 2020..2025.
TODAY = date(2026, 10, 1)
PHONE = "050-123-4567"
TABLES = ("users", "audit_log", "user_keys", "profiles", "life_events", "questionnaire_answers")


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


def make_client(
    sessionmaker: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> httpx.AsyncClient:
    settings = settings or Settings(env="test", cookie_secure=False, otp_resend_cooldown_seconds=0)
    app = create_app(
        settings,
        redis=fakeredis.FakeAsyncRedis(),
        sessionmaker=sessionmaker,
        storage=InMemoryObjectStorage(),
    )
    app.state.today = lambda: TODAY
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client(sessionmaker) as c:
        yield c


async def login(client: httpx.AsyncClient, phone: str = PHONE) -> httpx.Response:
    r = await client.post("/api/auth/request-otp", json={"phone": phone})
    assert r.status_code == 202, r.text
    sms = (await client.post("/api/dev/last-sms", json={"phone": phone})).json()["text"]
    code = re.search(r"\b(\d{6})\b", sms).group(1)  # type: ignore[union-attr]
    return await client.post("/api/auth/verify-otp", json={"phone": phone, "code": code})


# A complete questionnaire with every optional benefit answered 'no'.
ALL_NO: dict[str, object] = {
    "resident": True,
    "sex": "female",
    "marital_status": "married",
    "has_children": False,
    "has_degree": False,
    "discharged": False,
    "aliyah": False,
    "disability": False,
    "multiple_employers": False,
    "partial_year": False,
    "donations": False,
    "life_insurance": False,
    "pension_self": False,
    "localities": [{"name": "חיפה", "from_year": 2015, "to_year": None}],
}
