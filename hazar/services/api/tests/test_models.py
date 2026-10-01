from __future__ import annotations

import asyncio

import pytest
from alembic import command
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from hazar_api import audit
from hazar_api.models import AuditLog, Role, User

from .conftest import alembic_config


async def test_user_defaults(db: AsyncSession) -> None:
    user = User(phone="+972501234567")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.role is Role.USER
    assert user.created_at is not None
    assert user.verified_at is None


async def test_phone_is_unique(db: AsyncSession) -> None:
    db.add(User(phone="+972501234567"))
    await db.commit()
    db.add(User(phone="+972501234567"))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_audit_log_is_append_only(db: AsyncSession) -> None:
    user = User(phone="+972501234567")
    db.add(user)
    await db.flush()
    await audit.record(db, "auth.login", actor_id=user.id, target=f"user:{user.id}")
    await db.commit()

    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(update(AuditLog).values(action="tampered"))
    await db.rollback()

    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(delete(AuditLog))
    await db.rollback()


async def test_deleting_user_keeps_audit_rows(db: AsyncSession) -> None:
    user = User(phone="+972501234567")
    db.add(user)
    await db.flush()
    await audit.record(db, "auth.login", actor_id=user.id)
    await db.commit()

    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()

    row = (await db.execute(select(AuditLog))).scalar_one()
    assert row.actor_id is None
    assert row.action == "auth.login"


async def test_migrations_round_trip(database_url: str, engine: AsyncEngine, db: AsyncSession) -> None:
    await db.close()
    cfg = alembic_config(database_url)
    # Alembic's env.py runs its own event loop, so run it in a thread.
    await asyncio.to_thread(command.downgrade, cfg, "base")
    await asyncio.to_thread(command.upgrade, cfg, "head")
    tables = await db.scalars(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    )
    assert {"users", "audit_log", "user_keys", "alembic_version"} <= set(tables)
    await db.close()
    # Recreated enum types get new OIDs; drop pooled connections that cached the old ones.
    await engine.dispose()
