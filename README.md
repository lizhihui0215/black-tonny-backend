# Black Tonny Backend

Backend service repository for the Black Tonny retail analytics platform.

This repo owns the API layer, serving-side projections, capture-to-serving data flow, and operational jobs used by the Black Tonny dashboard and related workflows.

## Current Status

- FastAPI service for `manifest`, page payloads, dashboard summary, jobs, status, and cost snapshots
- Two-database model:
  - `black_tonny_capture` for raw or near-raw captured payloads
  - `black_tonny_serving` for runtime tables and API-facing projections
- Bootstrap mode still supports `data/cache` and `data/sample` fallbacks while the serving projection model continues to evolve
- Dashboard summary is already served by `GET /api/dashboard/summary`
- Direct Yeusoft capture integration and full migration of the legacy analysis pipeline are still in progress

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 scripts/sync_black_tonny_samples.py
uvicorn app.main:app --reload
python -m pytest
```

## Key Environment Variables

- `CAPTURE_DB_URL`
- `SERVING_DB_URL`
- `ADMIN_API_TOKEN`
- `PAYLOAD_CACHE_DIR`
- `SAMPLE_DATA_DIR`

The settings loader reads values in this order:

1. Process environment
2. `.env.local`
3. `.env`

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md): runtime flow, core layers, and ownership boundaries
- [docs/README.md](./docs/README.md): topic-level documentation index
- [CONTRIBUTING.md](./CONTRIBUTING.md): contribution and documentation update rules

## Documentation Policy

This repository uses a strict documentation language split:

- public-facing standard docs must be written in English
- internal working docs must be written in Chinese

Public-facing standard docs include:

- `README.md`
- `ARCHITECTURE.md`
- `docs/README.md`
- `CONTRIBUTING.md`

## Repository Layout

```text
app/
  api/
  core/
  db/
  jobs/
  schemas/
  services/
data/
  sample/
  cache/
deploy/
docs/
scripts/
tests/
```

## Related Repositories

- Optional sibling frontend repo:
  - `../black-tonny-frontend`
- Optional sibling frontend architecture doc:
  - `../black-tonny-frontend/ARCHITECTURE.md`

These sibling links are helpful when working in the split local workspace, but this backend repo should remain understandable on its own.
