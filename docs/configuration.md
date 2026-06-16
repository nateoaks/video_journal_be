# Configuration

All configuration is read through a single typed `Settings` object built with
**pydantic-settings**. It lives in `src/app/core/config.py` and is the only place in the
codebase allowed to touch the environment.

## The Settings object

```python
# src/app/core/config.py
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    service_name: str = "app"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./data/journal.db"
    sqlite_busy_timeout_ms: int = 5000

    storage_backend: str = "local"
    media_root: Path = Path("media")
    output_root: Path = Path("outputs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`DATABASE_URL` is the full async SQLAlchemy connection string (driver included). It
defaults to a SQLite database at `./data/journal.db`; in Docker Compose it points at the
bind-mounted `/data` volume (`sqlite+aiosqlite:////data/journal.db`). The connection runs
in WAL mode with a `SQLITE_BUSY_TIMEOUT_MS` busy timeout and foreign-key enforcement
enabled per connection (see `src/app/db/session.py`). `STORAGE_BACKEND` selects the
storage adapter (`local` for now);
`MEDIA_ROOT` and `OUTPUT_ROOT` are filesystem paths (bind-mounted to `/media` and
`/outputs` in the container) and are typed as `pathlib.Path`.

## Rules

- **Never read `os.environ` / `os.getenv` outside `config.py`.** Every other module
  imports `get_settings()` and reads typed attributes.
- `get_settings()` is `@lru_cache`d — it is a process-wide singleton. Do not instantiate
  `Settings()` directly elsewhere.
- Field types are enforced by Pydantic. A missing required var or a bad type (e.g. a
  non-`Path` value where one is expected) raises a `ValidationError` at startup — this is
  intentional; fail fast.
- Env var names are the field names **upper-cased**: `database_url` ← `DATABASE_URL`.
  pydantic-settings matches case-insensitively by default.
- Secrets and connection strings come from the environment only. Never hardcode them and
  never commit `.env` (commit `.env.example` instead).

## Adding a new setting

1. Add a typed field (with a sensible default for local dev) to `Settings`.
2. Document it in `.env.example`.
3. Read it via `get_settings().my_field` wherever needed.

For grouped/nested config (e.g. a third-party service with several keys), prefer a nested
Pydantic model with `env_nested_delimiter="__"` over a flat list of loosely related fields.

## Injecting config

In application code, call `get_settings()` directly — it is cheap and cached:

```python
from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url)
```

In tests, override individual settings by constructing a `Settings(...)` with explicit
kwargs, or set env vars before import. Do not mutate the cached singleton in place.
