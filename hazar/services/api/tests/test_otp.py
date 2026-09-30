from __future__ import annotations

import asyncio
import re

import fakeredis
import pytest

from hazar_api.config import Settings
from hazar_api.otp import InvalidCodeError, OtpService, RateLimitedError, TooManyAttemptsError
from hazar_api.phones import InvalidPhoneError, normalize_il_mobile
from hazar_api.privacy import mask_phone
from hazar_api.sms import MockSmsProvider

PHONE = "+972501234567"


def make(**overrides: object) -> tuple[OtpService, MockSmsProvider, fakeredis.FakeAsyncRedis]:
    redis = fakeredis.FakeAsyncRedis()
    sms = MockSmsProvider(redis)
    settings = Settings(env="test", **overrides)  # type: ignore[arg-type]
    return OtpService(redis, sms, settings), sms, redis


async def sent_code(sms: MockSmsProvider, phone: str = PHONE) -> str:
    text = await sms.last_message(phone)
    assert text is not None
    match = re.search(r"\b(\d{6})\b", text)
    assert match
    return match.group(1)


@pytest.mark.parametrize(
    "raw",
    ["0501234567", "050-123-4567", "+972501234567", "+972 50 123 4567", "972501234567", "00972501234567"],
)
def test_normalize_phone(raw: str) -> None:
    assert normalize_il_mobile(raw) == PHONE


@pytest.mark.parametrize("raw", ["", "031234567", "050123456", "+14155552671", "abc", "05012345678"])
def test_reject_bad_phone(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_il_mobile(raw)


def test_mask_phone() -> None:
    assert mask_phone(PHONE) == "+9725******67"
    assert "1234" not in mask_phone(PHONE)


async def test_happy_path_and_single_use() -> None:
    otp, sms, _ = make()
    await otp.request(PHONE, "1.1.1.1")
    code = await sent_code(sms)
    await otp.verify(PHONE, code)
    with pytest.raises(InvalidCodeError):
        await otp.verify(PHONE, code)


async def test_code_not_stored_in_plaintext_and_keys_have_no_phone() -> None:
    otp, sms, redis = make()
    await otp.request(PHONE, "1.1.1.1")
    code = await sent_code(sms)
    for key in await redis.keys("otp:*"):
        assert PHONE.encode() not in key
        if await redis.type(key) == b"string":
            assert code.encode() not in (await redis.get(key) or b"")


async def test_wrong_code() -> None:
    otp, _, _ = make()
    await otp.request(PHONE, "1.1.1.1")
    with pytest.raises(InvalidCodeError):
        await otp.verify(PHONE, "000000x")


async def test_lockout_after_max_attempts() -> None:
    otp, sms, _ = make(otp_max_attempts=3)
    await otp.request(PHONE, "1.1.1.1")
    code = await sent_code(sms)
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(2):
        with pytest.raises(InvalidCodeError):
            await otp.verify(PHONE, wrong)
    with pytest.raises(TooManyAttemptsError):
        await otp.verify(PHONE, wrong)
    # The code is burned, even the right one fails now.
    with pytest.raises(InvalidCodeError):
        await otp.verify(PHONE, code)


async def test_code_expires() -> None:
    otp, sms, _ = make(otp_ttl_seconds=1)
    await otp.request(PHONE, "1.1.1.1")
    code = await sent_code(sms)
    await asyncio.sleep(1.2)
    with pytest.raises(InvalidCodeError):
        await otp.verify(PHONE, code)


async def test_resend_cooldown() -> None:
    otp, _, _ = make(otp_resend_cooldown_seconds=60)
    await otp.request(PHONE, "1.1.1.1")
    with pytest.raises(RateLimitedError) as err:
        await otp.request(PHONE, "1.1.1.1")
    assert 0 < err.value.retry_after <= 60


async def test_per_phone_hourly_limit() -> None:
    otp, _, redis = make(otp_max_requests_per_phone_per_hour=2)
    for _ in range(2):
        await otp.request(PHONE, "1.1.1.1")
        for key in await redis.keys("otp:cooldown:*"):
            await redis.delete(key)
    with pytest.raises(RateLimitedError):
        await otp.request(PHONE, "1.1.1.1")


async def test_per_ip_hourly_limit() -> None:
    otp, _, _ = make(otp_max_requests_per_ip_per_hour=2)
    await otp.request("+972501111111", "9.9.9.9")
    await otp.request("+972502222222", "9.9.9.9")
    with pytest.raises(RateLimitedError):
        await otp.request("+972503333333", "9.9.9.9")
    await otp.request("+972503333333", "8.8.8.8")
