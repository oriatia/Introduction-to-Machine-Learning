from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hazar_api import audit
from hazar_api.config import Settings
from hazar_api.db import get_db
from hazar_api.models import Role, User
from hazar_api.otp import OtpService
from hazar_api.sessions import SessionStore

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_sessions(request: Request) -> SessionStore:
    store: SessionStore = request.app.state.sessions
    return store


def get_otp(request: Request) -> OtpService:
    otp: OtpService = request.app.state.otp
    return otp


def client_ip(request: Request, settings: Settings) -> str:
    direct = request.client.host if request.client else "unknown"
    if settings.trusted_proxy_count <= 0:
        return direct
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if len(hops) >= settings.trusted_proxy_count:
        return hops[-settings.trusted_proxy_count]
    return direct


async def current_user(
    request: Request,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    sessions: Annotated[SessionStore, Depends(get_sessions)],
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    data = await sessions.get(token) if token else None
    user = await db.get(User, data.user_id) if data else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[..., Awaitable[User]]:
    """RBAC dependency. Role is read from the DB on every request, so role changes apply immediately."""

    async def dependency(request: Request, user: CurrentUser, db: DbSession) -> User:
        if user.role not in roles:
            await audit.record(
                db,
                "authz.denied",
                actor_id=user.id,
                target=request.url.path,
                details={"role": user.role.value},
            )
            await db.commit()
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return dependency
