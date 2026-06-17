from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend


@lru_cache
def get_storage() -> StorageBackend:
    """Return the configured storage backend singleton."""
    settings = get_settings()
    if settings.storage_backend == "local":
        from app.storage.local import LocalStorage

        return LocalStorage(settings.media_root)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend!r}")
