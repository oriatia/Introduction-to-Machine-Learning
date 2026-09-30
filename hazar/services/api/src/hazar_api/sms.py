from __future__ import annotations

import logging
from typing import Protocol

from redis.asyncio import Redis

from hazar_api.privacy import mask_phone

logger = logging.getLogger(__name__)

MOCK_OUTBOX_TTL_SECONDS = 600


class SmsProvider(Protocol):
    async def send(self, phone: str, text: str) -> None: ...


class MockSmsProvider:
    """Development/test provider: nothing leaves the machine.

    The last message per phone is kept in Redis so the dev-only endpoint and E2E tests can read it.
    """

    def __init__(self, redis: Redis, key_prefix: str = "mock_sms") -> None:
        self._redis = redis
        self._prefix = key_prefix

    def _key(self, phone: str) -> str:
        return f"{self._prefix}:{phone}"

    async def send(self, phone: str, text: str) -> None:
        await self._redis.set(self._key(phone), text, ex=MOCK_OUTBOX_TTL_SECONDS)
        logger.info("mock SMS to %s: %s", mask_phone(phone), text)

    async def last_message(self, phone: str) -> str | None:
        value = await self._redis.get(self._key(phone))
        return value.decode() if isinstance(value, bytes) else value


def make_sms_provider(name: str, redis: Redis) -> SmsProvider:
    if name == "mock":
        return MockSmsProvider(redis)
    raise ValueError(f"Unknown SMS provider: {name}")
