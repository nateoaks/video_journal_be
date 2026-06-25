# Project Architecture

## Philosophy

This service follows a strict **layered architecture**. A request flows down through
clearly separated layers, and each layer may only depend on the ones below it:

```
HTTP request
     ↓
  router.py        (FastAPI endpoints — parse/validate input, no logic)
     ↓
  service.py       (business logic — orchestration, validation, domain rules)
     ↓
  repository.py    (data access — SQLAlchemy queries only)
     ↓
  models.py        (SQLAlchemy ORM — the database schema)
```

**Golden rule:** routers are thin. They convert HTTP to a service call and a service
result back to HTTP. All business logic lives in services; all SQL lives in repositories.

**Boundary rule:** never return a SQLAlchemy model from a router. Validate it into a
Pydantic schema (`SomeRead.model_validate(entity)`) so the ORM never leaks across the
HTTP boundary.

## File Structure

```
src/app/
├── main.py                     ← create_app() factory + module-level `app`
│
├── core/
│   ├── config.py               ← Settings (pydantic-settings)
│   ├── logging.py              ← structlog configuration + get_logger
│   ├── middleware.py           ← request-id / log-context middleware
│   ├── exception_handlers.py   ← maps AppError → JSON response
│   └── lifespan.py             ← startup/shutdown (dispose engine, etc.)
│
├── db/
│   ├── base.py                 ← DeclarativeBase subclass `Base`
│   └── session.py              ← async engine, sessionmaker, get_session dependency
│
├── common/
│   ├── repository.py           ← BaseRepository[ModelT] generic data-access base
│   ├── exceptions.py           ← AppError, NotFoundError, ConflictError
│   └── media_response.py       ← build_media_response() Range-aware streamer
│
├── storage/
│   ├── base.py                 ← StorageBackend ABC (save/open/delete/exists/path_or_url)
│   ├── local.py                ← LocalStorage — maps keys to media_root on disk
│   ├── __init__.py             ← get_storage() factory (lru_cache'd singleton)
│   └── dependencies.py         ← StorageDep for FastAPI DI
│
├── media/
│   ├── ffprobe.py              ← async ffprobe wrapper for video and audio metadata
│   ├── ffmpeg.py               ← FFmpeg subprocess wrapper for transcoding
│   ├── normalize.py            ← video normalisation (H.264/AAC MP4)
│   ├── compile.py              ← compilation rendering (concat clips, optionally mix clip audio under soundtrack)
│   └── filmstrip.py            ← filmstrip sprite generation (extract N frames, tile to JPEG)
│
├── domains/                    ← one self-contained package per feature
│   ├── health/
│   │   ├── router.py
│   │   └── schemas.py
│   ├── items/                  ← reference domain (full stack)
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   └── router.py
│   ├── clips/                  ← video clip upload, normalisation, and playback
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── utils.py
│   ├── compilations/           ← render ordered, trimmed clips into MP4 (with optional audio mix)
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   ├── progress.py
│   │   └── utils.py
│   ├── soundtracks/            ← audio upload and streaming
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── utils.py
│   └── storage/                ← on-demand disk usage reporting
│       ├── schemas.py
│       ├── service.py
│       ├── dependencies.py
│       └── router.py
│
└── api/
    ├── deps.py                 ← shared FastAPI dependencies (e.g. SessionDep)
    └── router.py               ← aggregates domain routers under /api/v1
```

## Request flow (the items domain)

```
POST /api/v1/items
  └── items/router.py        create_item(data, service)
        └── items/service.py     ItemService.create(data)
              └── items/repository.py   ItemRepository.add(entity)
                    └── items/models.py      Item (INSERT)
        ← returns ItemRead.model_validate(item)
```

Dependencies are wired through FastAPI's DI system. A router endpoint declares
`service: ItemServiceDep`; that annotation resolves `get_item_service`, which builds an
`ItemService` from an `ItemRepository`, which receives the request-scoped `AsyncSession`.
You never construct a service or repository by hand inside an endpoint.

## Adding a new domain

1. Create `src/app/domains/<domain>/` with the six standard files.
2. Define the ORM model in `models.py` (see `docs/data-models.md`).
3. Define request/response schemas in `schemas.py`.
4. Implement `repository.py` (extends `BaseRepository`) and `service.py`.
5. Expose providers in `dependencies.py` (`Annotated[Service, Depends(...)]`).
6. Register the router in `src/app/api/router.py`.
7. Generate a migration for the new tables (see `docs/database-migrations.md`).
8. Add tests under `tests/domains/<domain>/`.

`app/main.py` and `app/api/router.py` are the only wiring points — domains never import
each other's internals. If two domains need the same logic, lift it into `app/common/`.

## What never to do

| Don't | Do instead |
|---|---|
| Put business logic in `router.py` | Move it to `service.py` |
| Write raw SQL / `session.execute` in a service | Add a method to the repository |
| Return a SQLAlchemy model from an endpoint | Convert to a Pydantic `*Read` schema |
| Import `domains.a.service` from `domains.b` | Lift shared code into `common/` |
| Read `os.environ` anywhere | Use `Settings` (see `docs/configuration.md`) |
| `print()` for diagnostics | Use the structlog logger (see `docs/logging.md`) |
| Construct a service with `ItemService(...)` in an endpoint | Inject it via `dependencies.py` |
| Use `open()`, `os.path`, or `shutil` for media files | Use `StorageDep` (see `app/storage/`) |
