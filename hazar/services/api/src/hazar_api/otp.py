from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from redis.asyncio import Redis

from hazar_api.config import Settings
from hazar_api.privacy import keyed_hash
from hazar_api.sms import SmsProvider

# SMS body. User-facing copy; the product owner reviews wording together with he.json.
OTP_SMS_TEMPLATE_HE = "קוד האימות שלך ל-Hazar: {code}. הקוד בתוקף ל-{minutes} דקות. אין למסור אותו לאף אחד."


class OtpError(Exception):
    code = "otp_error"


class RateLimitedError(OtpError):
    code = "rate_limited"

    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = max(retry_after, 1)


class InvalidCodeError(OtpError):
    code = "invalid_code"


class TooManyAttemptsError(OtpError):
    code = "too_many_attempts"


@dataclass(frozen=True)
class _Keys:
    code: str
    attempts: str
    cooldown: str
    phone_window: str


class OtpService:
    """One-time codes stored only as HMACs in Redis, keyed by a hash of the phone (no PII in keys)."""

    def __init__(self, redis: Redis, sms: SmsProvider, settings: Settings) -> None:
        self._redis = redis
        self._sms = sms
        self._s = settings
        self._secret = settings.secret_bytes

    def _keys(self, phone: str) -> _Keys:
        h = keyed_hash(self._secret, phone)
        return _Keys(f"otp:code:{h}", f"otp:attempts:{h}", f"otp:cooldown:{h}", f"otp:window:phone:{h}")

    def _code_hash(self, phone: str, code: str) -> str:
        return keyed_hash(self._secret, f"{phone}:{code}")

    async def _hit_window(self, key: str, limit: int, window: int = 3600) -> None:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window)
        if count > limit:
            ttl = await self._redis.ttl(key)
            raise RateLimitedError(ttl if ttl > 0 else window)

    async def request(self, phone: str, client_ip: str) -> None:
        k = self._keys(phone)
        ip_key = f"otp:window:ip:{keyed_hash(self._secret, client_ip)}"
        await self._hit_window(ip_key, self._s.otp_max_requests_per_ip_per_hour)
        cooldown = self._s.otp_resend_cooldown_seconds  # 0 disables the cooldown (tests only)
        if cooldown > 0 and not await self._redis.set(k.cooldown, "1", nx=True, ex=cooldown):
            raise RateLimitedError(await self._redis.ttl(k.cooldown))
        await self._hit_window(k.phone_window, self._s.otp_max_requests_per_phone_per_hour)

        code = "".join(secrets.choice("0123456789") for _ in range(self._s.otp_length))
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(k.code, self._code_hash(phone, code), ex=self._s.otp_ttl_seconds)
            pipe.delete(k.attempts)
            await pipe.execute()
        minutes = max(self._s.otp_ttl_seconds // 60, 1)
        await self._sms.send(phone, OTP_SMS_TEMPLATE_HE.format(code=code, minutes=minutes))

    async def verify(self, phone: str, code: str) -> None:
        """Raises on failure. A code is single-use and dies after `otp_max_attempts` wrong guesses."""
        k = self._keys(phone)
        stored = await self._redis.get(k.code)
        if stored is None:
            raise InvalidCodeError
        attempts = await self._redis.incr(k.attempts)
        await self._redis.expire(k.attempts, self._s.otp_ttl_seconds)
        if attempts > self._s.otp_max_attempts:
            await self._redis.delete(k.code, k.attempts)
            raise TooManyAttemptsError
        expected = stored.decode() if isinstance(stored, bytes) else str(stored)
        if not hmac.compare_digest(expected, self._code_hash(phone, code)):
            if attempts == self._s.otp_max_attempts:
                await self._redis.delete(k.code, k.attempts)
                raise TooManyAttemptsError
            raise InvalidCodeError
        await self._redis.delete(k.code, k.attempts)
