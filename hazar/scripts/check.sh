#!/usr/bin/env bash
# Everything CI runs, runnable locally. Needs Postgres (HAZAR_TEST_DATABASE_URL) for API tests.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== python: lint, format, types"
uv run ruff check .
uv run ruff format --check .
for pkg in services/api services/worker packages/tax_engine; do uv run mypy "$pkg"; done

echo "== python: tests"
uv run pytest -q

echo "== web: lint, types, unit tests"
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web test
