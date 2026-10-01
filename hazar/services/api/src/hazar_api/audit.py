from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hazar_api.models import AuditLog


async def record(
    db: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    target: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add an audit row to the current transaction. Callers must not put PII in `target` or `details`."""
    db.add(AuditLog(actor_id=actor_id, action=action, target=target, details=details or {}))
    await db.flush()
