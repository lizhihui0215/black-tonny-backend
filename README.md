# Black Tonny Backend

Backend service repository for the Black Tonny retail analytics platform.

This repo owns the API layer, serving-side projections, capture-to-serving data flow, AI assistant backend contracts, and operational jobs used by the Black Tonny dashboard and related workflows.

Backend internal structure is now explicitly aligned to the local `FastAPI-boilerplate` baseline. Research and Playwright evidence remain important inputs, but they are not allowed to define the long-term runtime architecture. Use [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md) for the structural baseline and [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md) for the complete migration sequence.

## Current Status

- FastAPI service for `manifest`, page payloads, dashboard summary, assistant chat, jobs, status, and cost snapshots
- Formal frontend auth now runs through backend `/api/auth/*` and `/api/user/info`; the frontend repo-owned `apps/backend-mock` only remains as the local dev/test fallback, while backend runtime responsibility still covers page data, dashboard summary, assistant chat, jobs, and status APIs
- Two-database model:
  - `black_tonny_capture` for raw or near-raw captured payloads
  - `black_tonny_serving` for runtime tables and API-facing projections
- Bootstrap mode still supports `data/cache` and `data/sample` fallbacks while the serving projection model continues to evolve
- Dashboard summary is already served by `GET /api/dashboard/summary`
- Right-side assistant chat is served by `POST /api/assistant/chat`
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
- [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md): backend structure baseline and migration rules aligned to `FastAPI-boilerplate`
- [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md): complete migration phases from the current transitional backend to the boilerplate-aligned target structure
- [docs/api-response-standard.md](./docs/api-response-standard.md): default success envelope standard for formal backend `/api/*` routes
- [docs/frontend-auth-api.md](./docs/frontend-auth-api.md): current backend frontend-auth contract for the split frontend/backend runtime
- [docs/assistant/chat-api.md](./docs/assistant/chat-api.md): contract and ownership boundary for the right-side assistant chat endpoint
- [docs/tooling/README.md](./docs/tooling/README.md): repo-local tooling docs for MCP, browser research, and AI-assisted workflows
- [docs/erp/api-maturity-board.md](./docs/erp/api-maturity-board.md): generated ERP route maturity and trust state entrypoint
- [docs/erp/capture-route-registry.md](./docs/erp/capture-route-registry.md): current-account-visible route to capture mapping
- [Optional sibling frontend product docs (local workspace link)](../black-tonny-frontend/docs/product/README.md): customer-facing product overview and solution entrypoint
- [CONTRIBUTING.md](./CONTRIBUTING.md): contribution and documentation update rules

## AI Entry Docs

- [AGENTS.md](./AGENTS.md): vendor-neutral AI entrypoint, precedence, and repo-wide documentation rules
- [CLAUDE.md](./CLAUDE.md): Claude adapter for the shared AI entry standard
- [GEMINI.md](./GEMINI.md): Gemini adapter for the shared AI entry standard
- [.claude/CLAUDE.md](./.claude/CLAUDE.md): Claude compatibility shim that points to the root adapter

## Documentation Policy

This repository uses a strict documentation language split:

- public-facing standard docs must be written in English
- internal working docs must be written in Chinese

Public-facing standard docs include:

- `README.md`
- `ARCHITECTURE.md`
- `docs/README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.claude/CLAUDE.md`

## Repository Layout

```text
app/
  api/
  core/
  crud/        # boilerplate-aligned target layer; currently scaffolding-first
  db/          # transitional, to be aligned under boilerplate-style boundaries
  jobs/
  middleware/  # boilerplate-aligned target layer; currently scaffolding-first
  models/      # boilerplate-aligned target layer; currently scaffolding-first
  schemas/
  services/    # transitional orchestration-heavy area; new formal code should prefer capture/runtime/research/serving subpackages
data/
  sample/
  cache/
deploy/
docs/
scripts/
tests/
```

For the target backend module layout and migration boundary, use [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md), [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md), and [ARCHITECTURE.md](./ARCHITECTURE.md) together.

## Related Repositories

- [Optional sibling frontend repo (local workspace link)](../black-tonny-frontend)
- [Optional sibling frontend architecture doc (local workspace link)](../black-tonny-frontend/ARCHITECTURE.md)

These sibling links are helpful when working in the split local workspace, but this backend repo should remain understandable on its own.
