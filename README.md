# Video_journal_be

FastAPI backend built with async SQLAlchemy 2.0, PostgreSQL, and Alembic. Managed with uv.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com) (for local Postgres)
- Python 3.13 (uv will install it if missing)

## Setup

```bash
uv sync                       # install dependencies into .venv
cp .env.example .env          # then fill in values
docker compose up -d          # start Postgres
uv run poe makemigration m="initial schema"
uv run poe migrate            # apply migrations
```

## Running the app

```bash
uv run poe dev                # fastapi dev — http://localhost:8000
```

Interactive API docs: http://localhost:8000/docs

## Database migrations

```bash
uv run poe makemigration m="add something"   # autogenerate from model changes
uv run poe migrate                           # apply pending migrations
uv run alembic downgrade -1                   # roll back the last migration
uv run alembic current                        # show the applied revision
```

## Quality checks

```bash
uv run poe check     # ruff format + ruff check + mypy + pytest (run before every PR)
uv run poe format    # format + autofix lint
uv run poe lint      # lint only
uv run poe typecheck # mypy --strict
uv run poe test      # pytest
```

## Project structure

```
src/app/
├── core/       — Settings, logging, lifespan, middleware, exception handlers
├── db/         — SQLAlchemy Base, async engine + session
├── common/     — Shared base repository and error types
├── domains/    — Feature modules (models, schemas, repository, service, router)
└── api/        — Aggregated versioned router (/api/v1) + shared deps
```

See [CLAUDE.md](CLAUDE.md) and the [docs/](docs/) folder for architecture and conventions.
