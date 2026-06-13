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
