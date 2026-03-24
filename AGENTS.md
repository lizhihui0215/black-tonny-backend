# Black Tonny Backend Agent Guide

This file is the vendor-neutral AI entrypoint for `black-tonny-backend`.

Use it to find the canonical backend docs and collaboration rules. Do not treat this file as a second source of truth.

## Purpose

- define read order and doc precedence for AI-assisted work
- point to the current backend standards and deeper working docs
- keep vendor-specific adapter files thin and aligned

## Precedence

If instructions differ, follow this order:

1. Direct task, runtime, or maintainer instructions
2. [README.md](./README.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [docs/README.md](./docs/README.md), and [CONTRIBUTING.md](./CONTRIBUTING.md)
3. Relevant deeper docs such as [docs/two-database-architecture.md](./docs/two-database-architecture.md) and [docs/frontend-backend-boundary.md](./docs/frontend-backend-boundary.md)
4. This file
5. [CLAUDE.md](./CLAUDE.md), [.claude/CLAUDE.md](./.claude/CLAUDE.md), and [GEMINI.md](./GEMINI.md)

## Required Read Order

Before changing code or docs, read in this order:

1. [README.md](./README.md)
2. The relevant section or sections of [ARCHITECTURE.md](./ARCHITECTURE.md) that match the runtime layer or ownership boundary you may touch
3. The relevant entry in [docs/README.md](./docs/README.md) that points to the deeper docs for your area
4. Only the deeper docs that match the area you touch before changing behavior, contracts, or documented rules

Common deeper docs, open them when the task crosses those boundaries:

- [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md)
- [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md)
- [docs/api-response-standard.md](./docs/api-response-standard.md)
- [docs/two-database-architecture.md](./docs/two-database-architecture.md)
- [docs/frontend-backend-boundary.md](./docs/frontend-backend-boundary.md)

If the task involves MCP, Playwright research, repo-local research scripts, or other AI-assisted tooling, also read:

- [docs/tooling/README.md](./docs/tooling/README.md)
- [docs/tooling/ai-token-playbook.md](./docs/tooling/ai-token-playbook.md)

## Task Routing And Minimum Read Set

Use the smallest read set that still covers the boundary you may change.

| Task type | Minimum read set | Expand only when |
| --- | --- | --- |
| Small scoped code fix or test update inside an existing backend layer | [README.md](./README.md), the relevant section of [ARCHITECTURE.md](./ARCHITECTURE.md), the matching entry in [docs/README.md](./docs/README.md), and the target code or test files | the change alters API shape, auth behavior, data flow, ownership boundaries, or source-of-truth docs |
| API, schema, assistant, dashboard, or auth contract change | [README.md](./README.md), the API and service sections of [ARCHITECTURE.md](./ARCHITECTURE.md), [docs/README.md](./docs/README.md), [docs/api-response-standard.md](./docs/api-response-standard.md), and the matching area contract doc | the change also affects capture or serving ownership, cross-repo responsibilities, or shared frontend-backend boundaries |
| Capture, serving, jobs, or projection flow change | [README.md](./README.md), the data flow and database sections of [ARCHITECTURE.md](./ARCHITECTURE.md), [docs/README.md](./docs/README.md), [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md), [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md), and [docs/two-database-architecture.md](./docs/two-database-architecture.md) | the change also alters frontend expectations, API contracts, or dashboard-owned semantics |
| MCP, Playwright, research script, or AI-assisted workflow task | [README.md](./README.md), [docs/README.md](./docs/README.md), [docs/tooling/README.md](./docs/tooling/README.md), and [docs/tooling/ai-token-playbook.md](./docs/tooling/ai-token-playbook.md) | the tooling work touches formal runtime paths, capture admission, or business-source rules |
| Doc-only navigation, AI entry, or adapter maintenance | [README.md](./README.md), [docs/README.md](./docs/README.md), this file, and [docs/tooling/README.md](./docs/tooling/README.md) | the documentation update changes runtime ownership, public contracts, or repository-wide contribution rules |

## Low-Token Collaboration Defaults

- Start from one or two likely entry docs from the routing table above; do not pre-open every standard doc unless the task is boundary-spanning.
- Prefer scoped search with repo-local directories and task-specific keywords; avoid workspace-wide broad search unless local evidence is insufficient.
- Read targeted excerpts first and only scan full long docs when the task changes their owned boundary or the needed rule cannot be located otherwise.
- Keep progress updates to major checkpoints and avoid repeating the same repository facts after they are established.
- After each exploration round, keep a short fact cache with three lines: confirmed facts, excluded paths, and next step.
- If the task changes public contracts, runtime ownership, or source-of-truth rules, widen the read set before editing rather than guessing.
- Keep low-token collaboration guidance centralized in this file plus [docs/tooling/ai-token-playbook.md](./docs/tooling/ai-token-playbook.md); do not duplicate the same operating rules across unrelated area docs.

## Skill Policy

- Repository docs remain the source of truth.
- Adapter files point to those docs and should stay thin.
- Skills, if present, are optional execution helpers only; do not store repository rules only in a skill.
- If a skill and the repo docs ever differ, follow the repo docs and update or retire the skill.

## Documentation Language Policy

- Public-facing standard docs and AI entry docs must be written in English.
- Internal working docs under [docs/](./docs/README.md) must be written in Chinese.
- If an internal working doc is promoted into a public-facing standard doc, rewrite it in English as part of that promotion.

## Documentation Linking Policy

- Use Markdown hyperlinks for doc-to-doc navigation, source-of-truth references, and related-doc pointers.
- Do not rely on bare backticked file paths when the reader is expected to open another document.
- Navigation references must not be written as plain path text.

## File Naming Policy

- Use semantic filenames by default.
- Do not use numeric prefixes in Markdown filenames unless the file is explicitly allowlisted by the repository doc checker for a strict tutorial, manual, or runbook sequence.

## Verification Expectations

- Run the relevant verification for the area you changed.
- For doc-only changes, at minimum check links, naming consistency, and ownership statements.
- If runtime flow, jobs, or API contracts change, update the matching standard docs in the same change.

## Backend-Specific Pointers

- [README.md](./README.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [docs/README.md](./docs/README.md)
- [docs/backend-boilerplate-alignment.md](./docs/backend-boilerplate-alignment.md)
- [docs/backend-boilerplate-migration-roadmap.md](./docs/backend-boilerplate-migration-roadmap.md)
- [docs/api-response-standard.md](./docs/api-response-standard.md)
- [docs/tooling/README.md](./docs/tooling/README.md)
- [docs/two-database-architecture.md](./docs/two-database-architecture.md)
- [docs/frontend-backend-boundary.md](./docs/frontend-backend-boundary.md)

## Adapter Rule

Vendor-specific files such as [CLAUDE.md](./CLAUDE.md), [.claude/CLAUDE.md](./.claude/CLAUDE.md), and [GEMINI.md](./GEMINI.md) are compatibility adapters only. Keep them thin and do not duplicate backend standards there.
