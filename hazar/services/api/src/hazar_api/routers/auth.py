from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from hazar_api import audit
from hazar_api.config import Settings
from hazar_api.deps import (
    CurrentUser,
    DbSession,
    client_ip,
    get_otp,
    get_sessions,
    get_settings_dep,
)
from hazar_api.models import Role, User
from hazar_api.otp import OtpError, OtpService, RateLimitedError
from hazar_api.phones import InvalidPhoneError, normalize_il_mobile
from hazar_api.privacy import mask_phone
from hazar_api.sessions import SessionStore

router = APIRouter(prefix="/api/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
OtpDep = Annotated[OtpService, Depends(get_otp)]
SessionsDep = Annotated[SessionStore, Depends(get_sessions)]


class RequestOtpIn(BaseModel):
    phone: str = Field(max_length=32)


class RequestOtpOut(BaseModel):
    status: str
    resend_after: int


class VerifyOtpIn(BaseModel):
    phone: str = Field(max_length=32)
    code: str = Field(pattern=r"^\d{4,8}$")


class UserOut(BaseModel):
    id: uuid.UUID
    role: Role
    phone_masked: str

    @classmethod
    def of(cls, user: User) -> UserOut:
        return cls(id=user.id, role=user.role, phone_masked=mask_phone(user.phone))


class VerifyOtpOut(BaseModel):
    user: UserOut
    is_new: bool


def _phone(raw: str) -> str:
    try:
        return normalize_il_mobile(raw)
    except InvalidPhoneError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_phone") from None


def _otp_error(err: OtpError) -> JSONResponse:
    if isinstance(err, RateLimitedError):
        return JSONResponse(
            {"error": err.code, "retry_after": err.retry_after},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(err.retry_after)},
        )
    return JSONResponse({"error": err.code}, status_code=status.HTTP_400_BAD_REQUEST)


@router.post("/request-otp", status_code=status.HTTP_202_ACCEPTED, response_model=RequestOtpOut)
async def request_otp(body: RequestOtpIn, request: Request, settings: SettingsDep, otp: OtpDep) -> object:
    """Same response whether or not the phone is registered: registration and login are one flow."""
    phone = _phone(body.phone)
    try:
        await otp.request(phone, client_ip(request, settings))
    except OtpError as err:
        return _otp_error(err)
    return RequestOtpOut(status="sent", resend_after=settings.otp_resend_cooldown_seconds)


@router.post("/verify-otp", response_model=VerifyOtpOut)
async def verify_otp(
    body: VerifyOtpIn,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
    otp: OtpDep,
    sessions: SessionsDep,
) -> object:
    phone = _phone(body.phone)
    try:
        await otp.verify(phone, body.code)
    except OtpError as err:
        await audit.record(db, "auth.otp_failed", details={"reason": err.code})
        return _otp_error(err)

    user = await db.scalar(select(User).where(User.phone == phone))
    is_new = user is None
    if user is None:
        user = User(phone=phone, verified_at=datetime.now(UTC))
        db.add(user)
        await db.flush()
    elif user.verified_at is None:
        user.verified_at = datetime.now(UTC)
    await audit.record(
        db, "auth.register" if is_new else "auth.login", actor_id=user.id, target=f"user:{user.id}"
    )

    token = await sessions.create(user.id)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return VerifyOtpOut(user=UserOut.of(user), is_new=is_new)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, db: DbSession, settings: SettingsDep, sessions: SessionsDep
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        data = await sessions.get(token)
        await sessions.delete(token)
        if data:
            await audit.record(db, "auth.logout", actor_id=data.user_id, target=f"user:{data.user_id}")
    response.delete_cookie(settings.session_cookie_name, path="/")
