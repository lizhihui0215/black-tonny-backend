# Black Tonny Backend

Standalone backend scaffold for Black Tonny retail analysis.

## What is in this repo

- FastAPI service for `manifest`, page payloads, jobs, status, and cost snapshots
- MySQL-ready app storage layer for jobs and cost data
- File-based payload cache and sample payload bootstrap
- Docker Compose and Nginx deployment skeleton for single-server deployment

## What is not in this repo yet

- Direct Yeusoft capture integration
- Full MySQL migration of the analysis pipeline from the legacy repository
- HTML export

## Local structure

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
scripts/
tests/
```

## Key commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 scripts/sync_black_tonny_samples.py
uvicorn app.main:app --reload
pytest
```

## Environment

Copy `.env.local.example` to `.env.local` for local development, or adapt `.env.production.example` for deployment.

Local development values should point both database URLs to the same local MySQL database:

- `ANALYSIS_DB_URL`
- `APP_DB_URL`
- `ADMIN_API_TOKEN`
- `LOCAL_MYSQL_ROOT_PASSWORD` for local database administration only
- `PAYLOAD_CACHE_DIR`
- `SAMPLE_DATA_DIR`

The settings loader reads environment values in this order:

1. process environment
2. `.env.local`
3. `.env`

## Current bootstrap mode

This first version serves payloads from:

1. `data/cache/` if rebuild has generated cache
2. `data/sample/` as fallback seed data

That means the new backend can run as an independent repository immediately while the MySQL analysis migration is still being wired in.

## Local real startup

```bash
brew install mysql@8.4
brew services start mysql@8.4
python3 scripts/sync_black_tonny_samples.py
source .venv/bin/activate
uvicorn app.main:app --reload
```

For this stage, the backend writes app storage tables into a single local MySQL database named `black_tonny`, while page payloads still come from `data/sample` and `data/cache`.
