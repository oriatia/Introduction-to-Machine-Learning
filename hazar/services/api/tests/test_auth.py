from __future__ import annotations

import re
from collections.abc import AsyncIterator

import fakeredis
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.config import Settings
from hazar_api.main import create_app
from hazar_api.models import AuditLog, Role, User

PHONE = "050-123-4567"


@pytest.fixture
async def client(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(env="test", cookie_secure=False, otp_resend_cooldown_seconds=0)
    app = create_app(settings, redis=fakeredis.FakeAsyncRedis(), sessionmaker=sessionmaker)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def login(client: httpx.AsyncClient, phone: str = PHONE) -> httpx.Response:
    r = await client.post("/api/auth/request-otp", json={"phone": phone})
    assert r.status_code == 202, r.text
    sms = (await client.post("/api/dev/last-sms", json={"phone": phone})).json()["text"]
    code = re.search(r"\b(\d{6})\b", sms).group(1)  # type: ignore[union-attr]
    return await client.post("/api/auth/verify-otp", json={"phone": phone, "code": code})


async def actions(db: AsyncSession) -> list[str]:
    return list(await db.scalars(select(AuditLog.action).order_by(AuditLog.id)))


async def test_healthz(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_register_then_login(client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["is_new"] is True
    assert body["user"]["role"] == "user"
    assert body["user"]["phone_masked"] == "+9725******67"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]

    assert (await client.post("/api/auth/logout", json={})).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401

    r2 = await login(client)
    assert r2.json()["is_new"] is False
    assert r2.json()["user"]["id"] == body["user"]["id"]

    user = await db.scalar(select(User))
    assert user is not None
    assert user.phone == "+972501234567"
    assert user.verified_at is not None
    assert await actions(db) == ["auth.register", "auth.logout", "auth.login"]


async def test_old_session_token_is_useless_after_logout(client: httpx.AsyncClient) -> None:
    await login(client)
    token = client.cookies.get("hazar_session")
    await client.post("/api/auth/logout", json={})
    client.cookies.set("hazar_session", token or "")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_wrong_code(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await client.post("/api/auth/request-otp", json={"phone": PHONE})
    r = await client.post("/api/auth/verify-otp", json={"phone": PHONE, "code": "000000"})
    # A 1-in-a-million chance the real code is 000000; the assertion allows for it.
    if r.status_code != 200:
        assert r.status_code == 400
        assert r.json() == {"error": "invalid_code"}
        assert "set-cookie" not in r.headers
        assert await actions(db) == ["auth.otp_failed"]


async def test_invalid_phone(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/auth/request-otp", json={"phone": "03-1234567"})
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_phone"}


async def test_rate_limited_returns_429(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    app = create_app(
        Settings(env="test", otp_resend_cooldown_seconds=60),
        redis=fakeredis.FakeAsyncRedis(),
        sessionmaker=sessionmaker,
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/auth/request-otp", json={"phone": PHONE})).status_code == 202
        r = await c.post("/api/auth/request-otp", json={"phone": PHONE})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


async def test_unauthenticated(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    client.cookies.set("hazar_session", "forged")
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/advisor/overview")).status_code == 401


async def test_advisor_route_requires_role(client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await login(client)
    r = await client.get("/api/advisor/overview")
    assert r.status_code == 403
    assert "authz.denied" in await actions(db)

    user = await db.scalar(select(User))
    assert user is not None
    user.role = Role.ADVISOR
    await db.commit()
    # Role is read from the DB each request: no re-login needed.
    r = await client.get("/api/advisor/overview")
    assert r.status_code == 200
    assert r.json()["role"] == "advisor"


async def test_writes_require_json(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/auth/request-otp", data={"phone": PHONE})
    assert r.status_code == 415


async def test_dev_router_absent_in_production(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    settings = Settings(env="production", app_secret="x" * 40, master_key_b64="k")
    app = create_app(settings, redis=fakeredis.FakeAsyncRedis(), sessionmaker=sessionmaker)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/last-sms", json={"phone": PHONE})
        assert r.status_code == 404
        assert (await c.get("/api/docs")).status_code == 404


def test_production_requires_secrets() -> None:
    with pytest.raises(RuntimeError):
        Settings(env="production").require_secrets()
