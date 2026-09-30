from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from hazar_api.deps import require_roles
from hazar_api.models import Role, User

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

AdvisorUser = Annotated[User, Depends(require_roles(Role.ADVISOR, Role.ADMIN))]


@router.get("/overview")
async def overview(user: AdvisorUser) -> dict[str, object]:
    """Placeholder for the advisor back office (Sprint 6)."""
    return {"queue": [], "role": user.role.value}
