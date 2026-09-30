from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment (prefix HAZAR_). Secrets have no usable defaults."""

    model_config = SettingsConfigDict(env_prefix="HAZAR_", env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+asyncpg://hazar:hazar@localhost:5432/hazar"
    redis_url: str = "redis://localhost:6379/0"

    # Used to HMAC OTP codes and sign file-download tokens. Must be set outside development/test.
    app_secret: SecretStr = SecretStr("")
    # Base64 of a 32-byte key-encryption key for per-user document keys (local KeyWrapper only).
    master_key_b64: SecretStr = SecretStr("")

    sms_provider: Literal["mock"] = "mock"

    session_cookie_name: str = "hazar_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = True
    # Number of reverse proxies in front of the API whose X-Forwarded-For entries we trust.
    trusted_proxy_count: int = 0

    otp_length: int = Field(default=6, ge=4, le=8)
    otp_ttl_seconds: int = Field(default=300, ge=1)
    otp_max_attempts: int = Field(default=5, ge=1)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0)
    otp_max_requests_per_phone_per_hour: int = 5
    otp_max_requests_per_ip_per_hour: int = 20

    s3_endpoint_url: str | None = None
    s3_bucket: str = "hazar-documents"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_region: str = "us-east-1"

    file_url_ttl_seconds: int = Field(default=120, ge=10, le=900)

    def require_secrets(self) -> None:
        if self.env == "production":
            if len(self.app_secret.get_secret_value()) < 32:
                raise RuntimeError("HAZAR_APP_SECRET must be at least 32 characters in production")
            if not self.master_key_b64.get_secret_value():
                raise RuntimeError("HAZAR_MASTER_KEY_B64 must be set in production")
            if self.otp_resend_cooldown_seconds < 30:
                raise RuntimeError("HAZAR_OTP_RESEND_COOLDOWN_SECONDS must be at least 30 in production")
            if not self.cookie_secure:
                raise RuntimeError("HAZAR_COOKIE_SECURE must be true in production")

    @property
    def secret_bytes(self) -> bytes:
        secret = self.app_secret.get_secret_value()
        if not secret:
            if self.env == "production":
                raise RuntimeError("HAZAR_APP_SECRET is not set")
            secret = "insecure-development-secret-do-not-use"  # noqa: S105
        return secret.encode()

    @property
    def dev_tools_enabled(self) -> bool:
        return self.env in ("development", "test") and self.sms_provider == "mock"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.require_secrets()
    return settings
