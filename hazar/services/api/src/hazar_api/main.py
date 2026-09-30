from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hazar_api.config import Settings, get_settings
from hazar_api.crypto import LocalKeyWrapper
from hazar_api.db import make_engine, make_sessionmaker
from hazar_api.otp import OtpService
from hazar_api.routers import advisor, auth, dev, files
from hazar_api.sessions import SessionStore
from hazar_api.sms import make_sms_provider
from hazar_api.storage import ObjectStorage, S3ObjectStorage
from hazar_api.vault import DocumentVault

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(
    settings: Settings | None = None,
    *,
    redis: Redis | None = None,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    storage: ObjectStorage | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = None
        if sessionmaker is None:
            engine = make_engine(settings.database_url)
            app.state.sessionmaker = make_sessionmaker(engine)
        if isinstance(app.state.storage, S3ObjectStorage):
            await app.state.storage.ensure_bucket()
        try:
            yield
        finally:
            if engine is not None:
                await engine.dispose()
            if redis is None:
                await app.state.redis.aclose()

    app = FastAPI(
        title="Hazar API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.env != "production" else None,
        openapi_url="/api/openapi.json" if settings.env != "production" else None,
    )
    r = redis or Redis.from_url(settings.redis_url)
    sms = make_sms_provider(settings.sms_provider, r)
    app.state.settings = settings
    app.state.redis = r
    app.state.sms = sms
    app.state.otp = OtpService(r, sms, settings)
    app.state.sessions = SessionStore(r, settings.session_ttl_seconds)
    if sessionmaker is not None:
        app.state.sessionmaker = sessionmaker
    app.state.storage = storage or S3ObjectStorage(
        settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key.get_secret_value(),
        secret_key=settings.s3_secret_key.get_secret_value(),
        region=settings.s3_region,
    )
    app.state.vault = DocumentVault(
        app.state.storage, LocalKeyWrapper(settings.master_key), settings.secret_bytes
    )

    @app.middleware("http")
    async def json_only_for_writes(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # CSRF defense in depth (with SameSite=Lax): cross-site forms can't send application/json.
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                return JSONResponse({"error": "json_required"}, status_code=415)
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(advisor.router)
    app.include_router(files.router)
    if settings.dev_tools_enabled:
        app.include_router(dev.router)
    return app


def app_factory() -> FastAPI:
    """Entry point for uvicorn --factory, so importing this module has no side effects."""
    return create_app()
