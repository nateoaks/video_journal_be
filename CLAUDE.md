# Backend (Python / FastAPI)

Always read the relevant doc in `docs/` before working in that area. Your training
data lags behind FastAPI, SQLAlchemy 2.0, and Pydantic v2 — the docs in this repo are
the source of truth for our conventions.

## Project Architecture

```
src/app/
├── core/         — Settings, logging, lifespan, middleware, exception handlers
├── db/           — SQLAlchemy Base, async engine + session, unit-of-work dependency
├── common/       — Shared building blocks (base repository, errors, pagination)
├── domains/      — Feature modules, one package per domain
│   └── <domain>/ — models, schemas, repository, service, dependencies, router
└── api/          — Aggregated versioned router (/api/v1) + shared dependencies
```

Each feature under `src/app/domains/` is a self-contained package with a fixed shape:

- `models.py` — SQLAlchemy 2.0 ORM models (the persistence layer)
- `schemas.py` — Pydantic v2 request/response models (never expose ORM models directly)
- `repository.py` — data access; extends `app.common.repository.BaseRepository`
- `service.py` — business logic; depends on the repository, raises domain errors
- `dependencies.py` — FastAPI providers that wire the service together
- `router.py` — `APIRouter` with thin endpoints that delegate to the service

`app/main.py` is a thin factory (`create_app()`) that configures logging, registers
middleware and exception handlers, and mounts routers. It contains no business logic.

## Tooling

Managed with **uv**. Lint and format with **ruff**, type-check with **mypy --strict**,
test with **pytest**. Run the full gate before reporting a task done:

```bash
uv run poe check    # ruff format + ruff check + mypy + pytest
```


## Reference Docs
@docs/architecture.md
@docs/configuration.md
@docs/data-models.md
@docs/database-migrations.md
@docs/logging.md
@docs/code-design.md
@docs/code-style.md
@docs/testing.md


# Engineering Team Pipeline

This repo uses a set of Claude Code skills that together form an autonomous engineering pipeline, from a raw ticket to an opened PR. This file is the map — read it before assuming how something should be invoked.

## Pipeline order

```
requirements-analyst → architect (conditional) → linear-implementation-plan → linear-implementation-build
                                                                                       │
                                                            ┌──────────────────────────┼──────────────────────────┐
                                                            ▼                          ▼                          ▼
                                                    test-runner-qa            code-reviewer            security-reviewer (conditional)
                                                                                                          performance-reviewer (conditional)
                                                                                                                    │
                                                                                                                    ▼
                                                                                                            documentation
```

Independent of the above (separate entry points, not part of a single ticket's flow):
- `dependency-upgrade` — scheduled/on-demand maintenance
- `release-prep` — cutting a release (versioning, CHANGELOG, tag — no deploy)

## How to run it

**Full pipeline, one ticket, hands-off except built-in checkpoints:**
```
/pipeline BLA-7
```
This runs the `eng-team-orchestrator` skill, which chains all four main stages automatically and only stops where a stage already has a human checkpoint (clarifying questions, draft/plan approval, diff approval). It does not add extra "continue?" gates between stages.

**One stage at a time, manual control:**
```
/requirements BLA-7
/architect <project or epic name>
/plan BLA-7
/build BLA-7
```

**Standalone review of an in-progress diff** (not tied to a ticket pipeline run):
```
/review
```
Runs code-reviewer + test-runner-qa always, security-reviewer and performance-reviewer conditionally based on what the diff touches.

**Maintenance, run independently:**
```
/deps      — dependency-upgrade
/release   — release-prep
```

## Where checkpoints actually are

Every "approval" in this pipeline is a real stop, not a formality:

- `requirements-analyst` — asks clarifying questions before drafting; asks for approval before writing back to the ticket.
- `architect` — same pattern, plus its decisions are expensive to reverse, so its clarifying step pushes harder on real tradeoffs.
- `linear-implementation-plan` — same pattern; checks against an architecture doc's constraints if one exists.
- `linear-implementation-build` — runs a check gate (lint/typecheck/test), then test-runner-qa/code-reviewer/security-reviewer/performance-reviewer/documentation, then **shows the full diff for explicit approval before committing anything**, then a second approval before push/PR.
- `release-prep` — **no autonomous path at all**; always asks before tagging or writing the CHANGELOG.
- `dependency-upgrade` — the one skill designed for *less* oversight: patch/minor bumps auto-PR without a pre-push approval (still gated on the check gate passing); major bumps need sign-off; CVE patches proceed regardless of bump size, with the breaking-change risk surfaced explicitly rather than hidden.

If you're ever unsure whether something just happened autonomously or is waiting on you, the answer is in the relevant skill's `SKILL.md` under "The autonomy line" (dependency-upgrade) or its checkpoint steps (everything else).

## Known limitations

- **Linear ticket fetching**: the primary path is `Linear:get_issue`. If that tool isn't loaded in a given session, skills fall back to `Linear:list_issues` with a query — but that fallback **truncates long descriptions** and points to a `get_issue` tool that, in the fallback case, isn't available. If a ticket's description looks cut off, the skill will say so and ask rather than proceeding on a partial spec. Don't assume a truncated-looking description in a transcript means the ticket itself is incomplete — check before concluding that.
- **No deploy step anywhere in this pipeline.** `release-prep` stops at a tagged, documented release. If your team needs an actual deploy trigger, that's not built yet — say so explicitly rather than assuming `/release` does it.
- **No orchestrator memory across sessions.** If a pipeline run is interrupted (you close the session mid-build, say), re-running `/pipeline <ticket>` re-checks ticket state from scratch (status, existing `## Requirements`/`## Implementation Plan` sections) rather than resuming from an internal checkpoint — which is generally safe since each stage already detects and asks about existing partial work, but worth knowing if a run seems to "redo" something.

## Adding a new skill

New skills go in `.claude/skills/<name>/SKILL.md` (project-scoped, ships with the repo) and should be added to the diagram above if they sit in the main pipeline, or to "independent entry points" if they don't. If it's meant to be reachable via slash command, add a one-line command file to `.claude/commands/`.
