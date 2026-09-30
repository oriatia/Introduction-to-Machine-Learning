"""PII helpers. Anything that might reach logs, analytics or an external LLM goes through here.

The full PII-masking function for LLM calls (ID numbers, bank accounts, names) arrives with the agents.
"""

from __future__ import annotations

import hashlib
import hmac


def mask_phone(phone: str) -> str:
    """'+972501234567' -> '+9725*****67'. Safe for logs."""
    if len(phone) < 6:
        return "***"
    return phone[:5] + "*" * (len(phone) - 7) + phone[-2:]


def keyed_hash(secret: bytes, value: str) -> str:
    """Stable, non-reversible identifier for PII used in cache keys and rate-limit buckets."""
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()
