"""Development-only helpers. Mounted only when env is development/test AND the SMS provider is the mock."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from hazar_api.phones import InvalidPhoneError, normalize_il_mobile
from hazar_api.sms import MockSmsProvider

router = APIRouter(prefix="/api/dev", tags=["dev"])


class PhoneIn(BaseModel):
    phone: str = Field(max_length=32)


@router.post("/last-sms")
async def last_sms(body: PhoneIn, request: Request) -> dict[str, str | None]:
    sms = request.app.state.sms
    if not isinstance(sms, MockSmsProvider):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        phone = normalize_il_mobile(body.phone)
    except InvalidPhoneError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_phone") from None
    return {"text": await sms.last_message(phone)}
