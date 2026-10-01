"""Envelope encryption: per-user data keys (DEK) wrapped by a master key-encryption key (KEK)."""

from __future__ import annotations

import os
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12


def new_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encrypt(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, blob: bytes, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad)


class KeyWrapper(Protocol):
    """Wraps DEKs with a KEK. Production implements this over a cloud KMS in an Israel region."""

    @property
    def id(self) -> str: ...

    def wrap(self, dek: bytes, context: bytes) -> bytes: ...

    def unwrap(self, wrapped: bytes, context: bytes) -> bytes: ...


class LocalKeyWrapper:
    """KEK held in process memory (from env). For local development and tests."""

    def __init__(self, master_key: bytes, key_id: str = "local-v1") -> None:
        if len(master_key) != 32:
            raise ValueError("master key must be 32 bytes")
        self._kek = master_key
        self._id = key_id

    @property
    def id(self) -> str:
        return self._id

    def wrap(self, dek: bytes, context: bytes) -> bytes:
        return encrypt(self._kek, dek, context)

    def unwrap(self, wrapped: bytes, context: bytes) -> bytes:
        return decrypt(self._kek, wrapped, context)
