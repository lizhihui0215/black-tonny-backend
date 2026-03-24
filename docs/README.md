# Backend Docs Index

This directory contains topic-level documentation for `black-tonny-backend`.


## Language Note

Top-level public entry docs in this repository are maintained in English:

- [`../README.md`](../README.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- [`../AGENTS.md`](../AGENTS.md)

AI entry adapters are also maintained in English:

- [`../CLAUDE.md`](../CLAUDE.md)
- [`../GEMINI.md`](../GEMINI.md)
- [`../.claude/CLAUDE.md`](../.claude/CLAUDE.md)

Internal working documents in `docs/` must be maintained in Chinese.

This repository therefore uses a strict split:

- public-facing standard docs: English
- internal working docs: Chinese

## Status Legend

- `Source of truth`: the canonical rule or contract for the topic
- `Working doc`: active internal collaboration material
- `Draft`: incomplete or evolving internal material
- `Reference`: supporting context that is useful but not normative

Generated state panels should still use one of the four status values above. If a doc is the generated current-state entrypoint, call that out explicitly in its description.

## Core Platform Docs

- [`backend-boilerplate-alignment.md`](./backend-boilerplate-alignment.md)
  - Backend internal structure baseline aligned to the local `FastAPI-boilerplate`
  - Current language: Chinese working doc
  - Status: `Source of truth`
- [`backend-boilerplate-migration-roadmap.md`](./backend-boilerplate-migration-roadmap.md)
  - Full migration phases from the current transitional backend to the boilerplate-aligned target structure
  - Current language: Chinese working doc
  - Status: `Source of truth`
- [`api-response-standard.md`](./api-response-standard.md)
  - Default success envelope standard for formal backend `/api/*` routes
  - Current language: Chinese working doc
  - Status: `Source of truth`
- [`frontend-auth-api.md`](./frontend-auth-api.md)
  - Current backend frontend-auth contract for the split frontend/backend runtime
  - Current language: Chinese working doc
  - Status: `Source of truth`
- [`assistant/chat-api.md`](./assistant/chat-api.md)
  - Contract and ownership boundary for the right-side AI assistant chat endpoint
  - Current language: Chinese working doc
  - Status: `Working doc`
- [`two-database-architecture.md`](./two-database-architecture.md)
  - Current capture/serving database split and table-level responsibilities
  - Current language: Chinese working doc
  - Status: `Source of truth`
- [`frontend-backend-boundary.md`](./frontend-backend-boundary.md)
  - Cross-repository collaboration boundary between frontend and backend
  - Current language: Chinese collaboration doc
  - Status: `Working doc`

## Cross-Repository Product Entry

If you entered from the backend repo but need customer-facing or solution-facing platform docs, use the optional sibling frontend entrypoints:

- [Optional sibling frontend product docs (local workspace link)](../../black-tonny-frontend/docs/product/README.md)
  - Customer-facing product overview and solution brief entrypoint
  - Current language: Chinese
  - Status: `Working doc`
- [Optional sibling frontend document map (local workspace link)](../../black-tonny-frontend/docs/document-map.md)
  - Cross-repository navigation for product, implementation, tooling, and backend data docs
  - Current language: Chinese
  - Status: `Reference`

## Tooling Docs

- [`tooling/README.md`](./tooling/README.md)
  - Repo-local tooling docs, AI collaboration boundary, and adapter usage entrypoint
  - Current language: Chinese
  - Status: `Reference`
- [`tooling/ai-token-playbook.md`](./tooling/ai-token-playbook.md)
  - Low-token collaboration defaults for AI-assisted repo work
  - Current language: Chinese
  - Status: `Reference`
- [`tooling/mcp-guide.md`](./tooling/mcp-guide.md)
  - MCP usage boundary, config location, and FAQ
  - Current language: Chinese
  - Status: `Reference`
- [`tooling/browser-research-tools.md`](./tooling/browser-research-tools.md)
  - Playwright research tooling, profile, artifact paths, and usage boundary
  - Current language: Chinese
  - Status: `Reference`

## Dashboard Docs

Recommended reading order:

1. [Optional sibling frontend `evolution-log.md` (local workspace link)](../../black-tonny-frontend/docs/dashboard/evolution-log.md) - Cross-repository dashboard mainline and current boundary. Current language: Chinese.
   - Status: `Working doc`
2. [`dashboard/summary-api.md`](./dashboard/summary-api.md) - API contract for `GET /api/dashboard/summary`. Current language: Chinese.
   - Status: `Source of truth`
3. [`dashboard/summary-capture-mapping.md`](./dashboard/summary-capture-mapping.md) - Draft mapping between capture-side fields and summary metrics. Current language: Chinese.
   - Status: `Draft`
4. [`dashboard/evolution-index.md`](./dashboard/evolution-index.md) - Backend-side dashboard evolution references and index notes. Current language: Chinese.
   - Status: `Working doc`

## ERP Research Docs

- [`erp/README.md`](./erp/README.md)
  - ERP research overview and entrypoint
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/api-maturity-board.md`](./erp/api-maturity-board.md)
  - Generated ERP API maturity board and readiness status entrypoint
  - Current language: Chinese
  - Status: `Source of truth`
- [`erp/capture-route-registry.md`](./erp/capture-route-registry.md)
  - 1:1 capture route registry for current-account-visible ERP routes
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/capture-ingestion-roadmap.md`](./erp/capture-ingestion-roadmap.md)
  - Capture-ingestion roadmap for ERP sources
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/sales-ledger.md`](./erp/sales-ledger.md)
  - Sales-domain source ledger
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/inventory-ledger.md`](./erp/inventory-ledger.md)
  - Inventory-domain source ledger
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/member-ledger.md`](./erp/member-ledger.md)
  - Member-domain source ledger
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/stored-value-ledger.md`](./erp/stored-value-ledger.md)
  - Stored-value domain ledger
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/payment-and-doc-ledger.md`](./erp/payment-and-doc-ledger.md)
  - Payment and document-domain ledger
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/cost-visibility-audit.md`](./erp/cost-visibility-audit.md)
  - Cost-field visibility audit
  - Current language: Chinese
  - Status: `Working doc`
- [`erp/page-research-runbook.md`](./erp/page-research-runbook.md)
  - Yeusoft-specific page research runbook
  - Current language: Chinese
  - Status: `Working doc`
