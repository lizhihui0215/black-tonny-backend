# Black Tonny Backend

Standalone backend scaffold for Black Tonny retail analysis.

## What is in this repo

- FastAPI service for `manifest`, page payloads, jobs, status, and cost snapshots
- MySQL-ready two-database storage layer for capture and serving data
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

Local development values should point to two MySQL databases:

- `CAPTURE_DB_URL`
- `SERVING_DB_URL`
- `ADMIN_API_TOKEN`
- `LOCAL_MYSQL_ROOT_PASSWORD` for local database administration only
- `PAYLOAD_CACHE_DIR`
- `SAMPLE_DATA_DIR`

The settings loader reads environment values in this order:

1. process environment
2. `.env.local`
3. `.env`

## Current bootstrap mode

This version serves payloads from:

1. `data/cache/` if rebuild has generated cache
2. `data/sample/` as fallback seed data

That means the new backend can run as an independent repository immediately while the MySQL-backed serving projection layer is still being wired in.

## Dashboard summary endpoint

The backend now exposes a dedicated summary contract for the dashboard top cards:

- `GET /api/dashboard/summary`

It accepts:

- `preset=today|yesterday|last7days|last30days|thisMonth|lastMonth|custom`
- `start_date`
- `end_date`

The current implementation is MySQL-ready but sample-first:

1. load `data/cache/dashboard_summary.json` if present
2. fall back to `data/sample/dashboard_summary.json`
3. keep date range and compare range logic in the service layer so the frontend can integrate immediately

## Database architecture

The backend now targets two long-lived databases:

- `black_tonny_capture`
  - stores raw or near-raw source payloads by capture batch
  - used by capture jobs and transformation jobs only
- `black_tonny_serving`
  - stores FastAPI runtime tables plus the current business-serving projection tables
  - all business APIs should read from this database, or use sample/cache fallback during bootstrap

Important boundary:

- `capture` is the more stable raw-data layer
- `serving` is currently an evolving projection layer for pages and APIs
- do not assume every serving table is already the final long-term model

The legacy single-database setup is no longer the target architecture. Old `APP_DB_URL` and `ANALYSIS_DB_URL` values are only kept as temporary compatibility fallbacks while local environments are being updated.

See [docs/two-database-architecture.md](docs/two-database-architecture.md) for the capture-table to serving-table mapping and the current batch flow.

## Dashboard Docs

Dashboard 相关文档建议按下面顺序阅读：

- [Summary API contract](docs/dashboard/03-summary-api.md)
- [Summary capture mapping draft](docs/dashboard/08-summary-capture-mapping.md)
- [Two-database architecture](docs/two-database-architecture.md)
- [Dashboard evolution index](docs/dashboard/07-evolution-index.md)

其中：

- `03-summary-api.md` 负责 `/api/dashboard/summary` 契约
- `08-summary-capture-mapping.md` 负责当前 summary 主线的 capture 字段映射草案
- `two-database-architecture.md` 负责 capture / serving 两库结构
- `07-evolution-index.md` 负责索引到前端主文档中的 Dashboard 演进记录

## ERP Research Docs

ERP 接口研究与数据分析文档现在统一收口在：

- [ERP 接口研究总览](docs/erp/README.md)
- [销售域台账](docs/erp/sales-ledger.md)
- [库存域台账](docs/erp/inventory-ledger.md)
- [会员域台账](docs/erp/member-ledger.md)
- [储值域台账](docs/erp/stored-value-ledger.md)
- [流水与单据域台账](docs/erp/payment-and-doc-ledger.md)
- [成本字段可见性审计](docs/erp/cost-visibility-audit.md)

这组文档主要负责：

- 记录已知接口、过滤条件、分页和视图枚举
- 标记可能导致漏数和失真的接口风险
- 区分“源接口”和“结果快照接口”
- 记录成本字段、吊牌价字段和角色可见性差异

## Local real startup

```bash
brew install mysql@8.4
brew services start mysql@8.4
python3 scripts/sync_black_tonny_samples.py
source .venv/bin/activate
uvicorn app.main:app --reload
```

For this stage, the backend writes runtime tables and current API-facing projection tables into `black_tonny_serving`, keeps raw source payloads in `black_tonny_capture`, and still allows page payloads to fall back to `data/sample` and `data/cache` during bootstrap.
