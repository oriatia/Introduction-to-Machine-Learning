from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, cast

from redis.asyncio import Redis


@dataclass(frozen=True)
class SessionData:
    user_id: uuid.UUID


class SessionStore:
    """Opaque session tokens. Redis stores only a SHA-256 of the token, so a Redis dump can't be replayed."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(token: str) -> str:
        return "session:" + hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _user_index(user_id: uuid.UUID) -> str:
        return f"user_sessions:{user_id}"

    async def create(self, user_id: uuid.UUID) -> str:
        token = secrets.token_urlsafe(32)
        key = self._key(token)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(key, json.dumps({"user_id": str(user_id)}), ex=self._ttl)
            pipe.sadd(self._user_index(user_id), key)
            pipe.expire(self._user_index(user_id), self._ttl)
            await pipe.execute()
        return token

    async def get(self, token: str) -> SessionData | None:
        raw = await self._redis.get(self._key(token))
        if raw is None:
            return None
        return SessionData(user_id=uuid.UUID(json.loads(raw)["user_id"]))

    async def delete(self, token: str) -> None:
        key = self._key(token)
        data = await self.get(token)
        await self._redis.delete(key)
        if data:
            await cast(Awaitable[int], self._redis.srem(self._user_index(data.user_id), key))

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        index = self._user_index(user_id)
        keys = await cast(Awaitable[set[Any]], self._redis.smembers(index))
        if keys:
            await self._redis.delete(*keys)
        await self._redis.delete(index)
