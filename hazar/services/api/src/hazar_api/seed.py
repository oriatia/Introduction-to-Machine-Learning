"""Idempotent development seed: `python -m hazar_api.seed`. Refuses to run in production.

Demo cases arrive with the Case model (Sprint 6); for now it creates one user per role.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from hazar_api.config import get_settings
from hazar_api.db import make_engine, make_sessionmaker
from hazar_api.models import Role, User

DEMO_USERS: list[tuple[str, Role]] = [
    ("+972500000001", Role.USER),
    ("+972500000002", Role.ADVISOR),
    ("+972500000003", Role.ADVISOR),
    ("+972500000009", Role.ADMIN),
]


async def seed() -> list[str]:
    settings = get_settings()
    if settings.env == "production":
        raise SystemExit("Refusing to seed a production database")
    engine = make_engine(settings.database_url)
    created: list[str] = []
    async with make_sessionmaker(engine)() as db:
        for phone, role in DEMO_USERS:
            user = await db.scalar(select(User).where(User.phone == phone))
            if user is None:
                db.add(User(phone=phone, role=role, verified_at=datetime.now(UTC)))
                created.append(f"{role.value}:{phone[-2:]}")
            else:
                user.role = role
        await db.commit()
    await engine.dispose()
    return created


if __name__ == "__main__":
    print("seeded:", ", ".join(asyncio.run(seed())) or "nothing new")
