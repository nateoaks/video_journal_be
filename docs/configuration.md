# Configuration

All configuration is read through a single typed `Settings` object built with
**pydantic-settings**. It lives in `src/app/core/config.py` and is the only place in the
codebase allowed to touch the environment.

## The Settings object

```python
# src/app/core/config.py
from functools import lru_cache

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

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"  # noqa: S105
    db_name: str = "app"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

## Rules

- **Never read `os.environ` / `os.getenv` outside `config.py`.** Every other module
  imports `get_settings()` and reads typed attributes.
- `get_settings()` is `@lru_cache`d — it is a process-wide singleton. Do not instantiate
  `Settings()` directly elsewhere.
- Field types are enforced by Pydantic. A missing required var or a bad type (e.g.
  `DB_PORT=abc`) raises a `ValidationError` at startup — this is intentional; fail fast.
- Env var names are the field names **upper-cased**: `db_host` ← `DB_HOST`. pydantic-settings
  matches case-insensitively by default.
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
