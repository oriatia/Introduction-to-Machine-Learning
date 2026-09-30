from __future__ import annotations

import os
import time
import uuid

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.crypto import LocalKeyWrapper, decrypt, encrypt, new_dek
from hazar_api.models import AuditLog, User, UserKey
from hazar_api.storage import InMemoryObjectStorage, S3ObjectStorage
from hazar_api.vault import DocumentVault, InvalidFileTokenError

from .conftest import make_client
from .test_auth import login

KEK = bytes(range(32))
SECRET = b"s" * 32
DOC = "טופס 106 — test document".encode()


async def make_user(db: AsyncSession, phone: str = "+972501234567") -> User:
    user = User(phone=phone)
    db.add(user)
    await db.flush()
    return user


def test_aead_round_trip_and_tamper() -> None:
    key = new_dek()
    blob = encrypt(key, b"hello", b"aad")
    assert decrypt(key, blob, b"aad") == b"hello"
    with pytest.raises(InvalidTag):
        decrypt(key, blob, b"other-aad")
    with pytest.raises(InvalidTag):
        decrypt(key, blob[:-1] + bytes([blob[-1] ^ 1]), b"aad")
    with pytest.raises(InvalidTag):
        decrypt(new_dek(), blob, b"aad")


async def test_storage_sees_only_ciphertext(db: AsyncSession) -> None:
    storage = InMemoryObjectStorage()
    vault = DocumentVault(storage, LocalKeyWrapper(KEK), SECRET)
    user = await make_user(db)

    key = await vault.put(db, user.id, DOC, "application/pdf")
    assert str(user.id) in key
    assert "+972" not in key
    assert DOC not in storage.objects[key].data
    got = await vault.get(db, user.id, key)
    assert got.data == DOC
    assert got.content_type == "application/pdf"

    row = await db.get(UserKey, user.id)
    assert row is not None
    assert row.key_wrapper_id == "local-v1"
    assert len(row.wrapped_dek) == 12 + 32 + 16  # nonce + wrapped key + tag


async def test_users_have_separate_keys_and_cannot_cross_read(db: AsyncSession) -> None:
    storage = InMemoryObjectStorage()
    vault = DocumentVault(storage, LocalKeyWrapper(KEK), SECRET)
    alice = await make_user(db, "+972501111111")
    bob = await make_user(db, "+972502222222")
    alice_key = await vault.put(db, alice.id, DOC, "text/plain")
    bob_key = await vault.put(db, bob.id, DOC, "text/plain")

    wrapped = list(await db.scalars(select(UserKey.wrapped_dek)))
    assert len(set(wrapped)) == 2

    with pytest.raises(PermissionError):
        await vault.get(db, bob.id, alice_key)
    # Ciphertext moved under another user's key path does not decrypt.
    storage.objects[bob_key] = storage.objects[alice_key]
    with pytest.raises(InvalidTag):
        await vault.get(db, bob.id, bob_key)


async def test_wrong_master_key_cannot_unwrap(db: AsyncSession) -> None:
    storage = InMemoryObjectStorage()
    user = await make_user(db)
    key = await DocumentVault(storage, LocalKeyWrapper(KEK), SECRET).put(db, user.id, DOC, "text/plain")
    with pytest.raises(InvalidTag):
        await DocumentVault(storage, LocalKeyWrapper(b"x" * 32), SECRET).get(db, user.id, key)


def test_file_tokens() -> None:
    vault = DocumentVault(InMemoryObjectStorage(), LocalKeyWrapper(KEK), SECRET)
    user_id = uuid.uuid4()
    key = f"users/{user_id}/{uuid.uuid4()}"
    grant = vault.verify_token(vault.signed_token(user_id, key, 60))
    assert grant.user_id == user_id
    assert grant.object_key == key

    with pytest.raises(InvalidFileTokenError):
        vault.verify_token(vault.signed_token(user_id, key, -1))
    token = vault.signed_token(user_id, key, 60)
    with pytest.raises(InvalidFileTokenError):
        vault.verify_token(token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1])
    with pytest.raises(InvalidFileTokenError):
        vault.verify_token("garbage")
    other = DocumentVault(InMemoryObjectStorage(), LocalKeyWrapper(KEK), b"t" * 32)
    with pytest.raises(InvalidFileTokenError):
        other.verify_token(token)
    # A token whose key is outside the user's prefix is rejected even if signed.
    with pytest.raises(InvalidFileTokenError):
        vault.verify_token(vault.signed_token(user_id, f"users/{uuid.uuid4()}/x", 60))


async def test_download_endpoint(sessionmaker: async_sessionmaker[AsyncSession], db: AsyncSession) -> None:
    async with make_client(sessionmaker) as alice, make_client(sessionmaker) as bob:
        # Both clients share the DB but not Redis; give bob his own app by logging in separately.
        await login(alice, "0501111111")
        await login(bob, "0502222222")
        app = alice._transport.app  # type: ignore[attr-defined]
        vault: DocumentVault = app.state.vault
        alice_user = await db.scalar(select(User).where(User.phone == "+972501111111"))
        assert alice_user is not None
        async with sessionmaker() as s:
            key = await vault.put(s, alice_user.id, DOC, "text/plain")
            await s.commit()
        token = vault.signed_token(alice_user.id, key, 60)

        r = await alice.get(f"/api/files/{token}")
        assert r.status_code == 200
        assert r.content == DOC
        assert r.headers["cache-control"] == "private, no-store"

        # Bob's app has a different Redis but the same signing secret (settings), so the token verifies;
        # ownership check must still refuse.
        r = await bob.get(f"/api/files/{token}")
        assert r.status_code == 404

    audit_actions = list(await db.scalars(select(AuditLog.action)))
    assert "document.read" in audit_actions
    assert "document.denied" in audit_actions


@pytest.mark.skipif(not os.environ.get("HAZAR_TEST_S3_ENDPOINT"), reason="HAZAR_TEST_S3_ENDPOINT not set")
async def test_s3_storage_round_trip(db: AsyncSession) -> None:
    storage = S3ObjectStorage(
        f"hazar-test-{int(time.time())}",
        endpoint_url=os.environ["HAZAR_TEST_S3_ENDPOINT"],
        access_key=os.environ.get("HAZAR_TEST_S3_ACCESS_KEY", "hazar-local"),
        secret_key=os.environ.get("HAZAR_TEST_S3_SECRET_KEY", "hazar-local-secret"),
        region="us-east-1",
    )
    await storage.ensure_bucket()
    vault = DocumentVault(storage, LocalKeyWrapper(KEK), SECRET)
    user = await make_user(db)
    key = await vault.put(db, user.id, DOC, "image/jpeg")
    raw = await storage.get(key)
    assert DOC not in raw.data
    got = await vault.get(db, user.id, key)
    assert got.data == DOC
    assert got.content_type == "image/jpeg"
    await vault.delete(user.id, key)
