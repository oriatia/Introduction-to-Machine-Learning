# Local development

## Full stack (Docker)

```bash
cd infra
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:3000 | Web app (Hebrew, RTL) |
| http://localhost:3000/design | Design-system demo |
| http://localhost:8000/api/docs | API docs (disabled in production) |

`migrate` runs Alembic and the seed, then exits. Seeded users (log in with any of them):

| Phone | Role |
|---|---|
| 050-0000001 | user |
| 050-0000002, 050-0000003 | advisor |
| 050-0000009 | admin |

### Getting the SMS code
The SMS provider is a mock: nothing is sent. The code is visible in either place:
- `docker compose logs -f api` (line `mock SMS to +9725******01: ...`)
- `curl -s -X POST localhost:3000/api/dev/last-sms -H 'Content-Type: application/json' -d '{"phone":"0500000001"}'`

`/api/dev/*` exists only when `HAZAR_ENV` is development/test **and** the SMS provider is the mock.

### Documents and extraction
Uploads are encrypted per user and extracted by the worker. Locally the extractor is the **mock**: a real photo
comes back with empty fields (type the values on the review screen); `apps/web/e2e/fixtures/form106-mock.png`
carries sample values so you can see a full extraction. To try Claude vision instead (ADR 0004 §4, needs the
product owner's privacy decision first): set `HAZAR_EXTRACTION_PROVIDER=claude`, `HAZAR_ALLOW_IMAGES_TO_LLM=true`
and `ANTHROPIC_API_KEY` on the `api` and `worker` services.

### Behind a TLS-intercepting proxy
If image builds fail with certificate errors, pass your proxy's CA bundle as a build secret
(it is never stored in an image): `HAZAR_EXTRA_CA_FILE=/path/to/ca.pem docker compose build`.

## Without Docker (fast loop)

Requirements: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22 + pnpm 10, and Postgres 16, Redis 7 and an
S3-compatible store running locally (e.g. `docker compose up postgres redis s3` with ports published).

```bash
uv sync --all-packages
pnpm install
(cd services/api && uv run alembic upgrade head && uv run python -m hazar_api.seed)
uv run uvicorn --factory hazar_api.main:app_factory --reload --port 8000
uv run arq hazar_worker.main.WorkerSettings
pnpm --filter web dev
```

## Checks

```bash
./scripts/check.sh          # lint, format, types, unit + integration tests (needs Postgres)
```

API tests use `HAZAR_TEST_DATABASE_URL` (default `postgresql+asyncpg://hazar:hazar@localhost:5432/hazar_test`;
the database is created and reset automatically). Optional integration tests run when these are set:
`HAZAR_TEST_S3_ENDPOINT` (+ `_ACCESS_KEY`, `_SECRET_KEY`) and `HAZAR_TEST_REDIS_URL`.

### End-to-end (Playwright)
Start the stack with relaxed OTP limits (the tests log the same phone in repeatedly), then run the tests:

```bash
cd infra
HAZAR_OTP_RESEND_COOLDOWN_SECONDS=0 HAZAR_OTP_MAX_REQUESTS_PER_IP_PER_HOUR=1000 \
HAZAR_OTP_MAX_REQUESTS_PER_PHONE_PER_HOUR=100 docker compose up -d --build
cd ../apps/web && pnpm exec playwright install chromium && pnpm test:e2e
```
