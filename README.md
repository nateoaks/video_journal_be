# Video_journal_be

FastAPI backend built with async SQLAlchemy 2.0, PostgreSQL, and Alembic. Managed with uv.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com) (for local Postgres / the full stack)
- Python 3.14 (uv will install it if missing)

## Repository layout

The backend and frontend live in **two sibling repositories**, checked out next to each
other:

```
video_journal/
├── video_journal_be/   ← this repo (FastAPI)
└── video_journal_fe/   ← Next.js frontend
```

The root `docker-compose.yml` lives here in the backend repo and builds the frontend via a
`../video_journal_fe` build context, so both repos must be cloned as siblings for the full
stack to come up from a clean checkout.

## Full stack with Docker Compose

```bash
docker compose up -d          # postgres + backend + frontend
```

- Frontend: http://localhost:3000 (proxies `/api/*` → backend via Next.js rewrites)
- Backend:  http://localhost:8000 — `GET /api/health` and `GET /health` return `200 OK`

All ports are bound to `127.0.0.1` only. The backend bind-mounts `./data`, `./media`, and
`./outputs` into the container. FFmpeg and `ffprobe` are installed in the backend image.

## Setup

```bash
uv sync                       # install dependencies into .venv
cp .env.example .env          # then fill in values
docker compose up -d postgres # start just Postgres for local dev
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
├── storage/    — StorageBackend abstraction + LocalStorage; inject via StorageDep
├── domains/    — Feature modules (models, schemas, repository, service, router)
└── api/        — Aggregated versioned router (/api/v1) + shared deps
```

See [CLAUDE.md](CLAUDE.md) and the [docs/](docs/) folder for architecture and conventions.
