# Contributing to Black Tonny Backend

Thanks for contributing.

This repository is part of a split frontend/backend workspace, but it should remain maintainable and understandable as an independent backend repository.

## Before You Change Anything

- read [README.md](./README.md) for the current repo status and entrypoints
- read [ARCHITECTURE.md](./ARCHITECTURE.md) before changing runtime flow, boundaries, or ownership
- read [docs/README.md](./docs/README.md) before editing topic-level documentation
- read [AGENTS.md](./AGENTS.md) when you work through an AI coding agent in this repo

## Development Expectations

- keep runtime behavior aligned with the current `capture` / `serving` boundary
- do not move backend-owned metric logic into the frontend
- avoid changing public API contracts without updating the relevant documentation
- prefer explicit, small changes over broad undocumented refactors

## Verification

Typical local verification flow:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m pytest
```

If your change affects startup, jobs, or payload serving, run the relevant local flow as well.

## Documentation Update Rules

Update the correct document for the type of change:

- `README.md`
  - quick start
  - current status
  - top-level documentation entrypoints
- `ARCHITECTURE.md`
  - runtime flow
  - core layering
  - ownership boundaries
  - data flow changes
- `docs/README.md`
  - topic-document index entries
  - language notes
  - new or removed topic docs
- `AGENTS.md`
  - AI entry precedence
  - required read order
  - shared documentation rules for AI-assisted work
- topic docs under `docs/`
  - API contracts
  - database details
  - ERP research and ledger content

## Documentation Naming And Linking Rules

- use semantic filenames for Markdown docs by default
- do not use numeric prefixes in Markdown filenames unless the repository doc checker explicitly allowlists the file for a strict tutorial, manual, or runbook sequence
- use Markdown hyperlinks for doc-to-doc navigation and source-of-truth references
- do not leave bare backticked file paths where the reader is expected to navigate

## Documentation Language Policy

Use the following language rule consistently:

- public-facing standard docs must be written in English
- internal working docs must be written in Chinese

In this repository, public-facing standard docs include:

- `README.md`
- `ARCHITECTURE.md`
- `docs/README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.claude/CLAUDE.md`

Internal docs include topic-level working materials under `docs/`, such as:

- API mapping drafts
- ERP research ledgers
- operational runbooks
- collaboration notes

If an internal working doc is later promoted into a public-facing standard doc, it must be rewritten in English as part of that promotion.

## Pull Requests

Please include:

- a clear summary of what changed
- any affected API contracts or data-flow boundaries
- the validation steps you ran
- documentation updates when the behavior or ownership model changed

## Commit Messages

Conventional-style commit messages are recommended, for example:

```text
docs(backend): refresh architecture entrypoints
fix(summary): correct serving fallback order
```
