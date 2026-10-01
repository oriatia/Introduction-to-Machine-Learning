# Hazar

Mobile-first, Hebrew/RTL web app that finds Israeli salaried employees tax refunds they are owed,
prepares Form 135 and routes it to a licensed tax advisor. See [`CLAUDE.md`](CLAUDE.md) for the full brief.

## Layout

| Path | What |
|---|---|
| `apps/web` | Next.js app (user + `/advisor` back office) |
| `services/api` | FastAPI API, models, Alembic migrations |
| `services/worker` | arq background jobs |
| `packages/tax_engine` | Pure-Python tax engine and per-year tables |
| `infra` | Docker Compose, Dockerfiles, seed |
| `docs` | Architecture notes and ADRs |

## Run locally

```bash
cd infra && docker compose up --build
```

Then open http://localhost:3000. See `docs/local-dev.md` for details.
