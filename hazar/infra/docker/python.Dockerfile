# syntax=docker/dockerfile:1
# Shared image for services/api and services/worker (uv workspace).
FROM python:3.12-slim

# Optional `extra_ca` build secret: a CA bundle for builds behind a TLS-intercepting proxy. Never baked into the image.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install --no-cache-dir uv==0.8.17
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY services/api/pyproject.toml services/api/
COPY services/worker/pyproject.toml services/worker/
COPY packages/tax_engine/pyproject.toml packages/tax_engine/
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev --all-packages --no-install-workspace

COPY packages packages
COPY services services
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev --all-packages

RUN useradd --system --uid 10001 app
USER app
