from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from hazar_api.crypto import KeyWrapper, decrypt, encrypt, new_dek
from hazar_api.models import UserKey
from hazar_api.storage import ObjectStorage, StoredObject


class InvalidFileTokenError(Exception):
    pass


@dataclass(frozen=True)
class FileGrant:
    user_id: uuid.UUID
    object_key: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class DocumentVault:
    """Stores user documents encrypted with that user's DEK. Storage only ever sees ciphertext.

    Object keys contain no PII (user UUID + random UUID). The object key is bound into the AEAD
    associated data, so ciphertext copied to another key or user fails to decrypt.
    """

    def __init__(self, storage: ObjectStorage, wrapper: KeyWrapper, signing_secret: bytes) -> None:
        self._storage = storage
        self._wrapper = wrapper
        self._secret = signing_secret

    async def _dek(self, db: AsyncSession, user_id: uuid.UUID) -> bytes:
        context = str(user_id).encode()
        row = await db.get(UserKey, user_id)
        if row is None:
            dek = new_dek()
            db.add(
                UserKey(
                    user_id=user_id,
                    wrapped_dek=self._wrapper.wrap(dek, context),
                    key_wrapper_id=self._wrapper.id,
                )
            )
            await db.flush()
            return dek
        return self._wrapper.unwrap(row.wrapped_dek, context)

    @staticmethod
    def _owns(user_id: uuid.UUID, object_key: str) -> bool:
        return object_key.startswith(f"users/{user_id}/")

    async def put(self, db: AsyncSession, user_id: uuid.UUID, data: bytes, content_type: str) -> str:
        object_key = f"users/{user_id}/{uuid.uuid4()}"
        dek = await self._dek(db, user_id)
        await self._storage.put(object_key, encrypt(dek, data, object_key.encode()), content_type)
        return object_key

    async def get(self, db: AsyncSession, user_id: uuid.UUID, object_key: str) -> StoredObject:
        if not self._owns(user_id, object_key):
            raise PermissionError("object does not belong to user")
        stored = await self._storage.get(object_key)
        dek = await self._dek(db, user_id)
        return StoredObject(decrypt(dek, stored.data, object_key.encode()), stored.content_type)

    async def delete(self, user_id: uuid.UUID, object_key: str) -> None:
        if not self._owns(user_id, object_key):
            raise PermissionError("object does not belong to user")
        await self._storage.delete(object_key)

    # Short-lived signed download tokens. Objects are app-encrypted, so a bucket presigned URL
    # would only serve ciphertext; instead the API decrypts behind a signed, expiring token.
    def _sign(self, payload: bytes) -> str:
        return _b64(hmac.new(self._secret, b"file-token:" + payload, hashlib.sha256).digest())

    def signed_token(self, user_id: uuid.UUID, object_key: str, ttl_seconds: int) -> str:
        payload = json.dumps(
            {"u": str(user_id), "k": object_key, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":")
        ).encode()
        return f"{_b64(payload)}.{self._sign(payload)}"

    def verify_token(self, token: str) -> FileGrant:
        try:
            payload_b64, sig = token.split(".", 1)
            payload = _unb64(payload_b64)
        except ValueError:
            raise InvalidFileTokenError from None
        if not hmac.compare_digest(sig, self._sign(payload)):
            raise InvalidFileTokenError
        data = json.loads(payload)
        if int(data["exp"]) < time.time():
            raise InvalidFileTokenError
        grant = FileGrant(uuid.UUID(data["u"]), data["k"])
        if not self._owns(grant.user_id, grant.object_key):
            raise InvalidFileTokenError
        return grant
