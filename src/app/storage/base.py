from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import BinaryIO


class StorageBackend(ABC):
    """Abstract interface for file storage backends."""

    @abstractmethod
    async def save(self, stream: AsyncIterator[bytes], key: str) -> str:
        """Write chunked stream to storage at key; return key."""

    @abstractmethod
    async def open(self, key: str) -> BinaryIO:
        """Return a readable binary file object for key; caller must close it."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the file at key. Idempotent — no error if already absent."""

    @abstractmethod
    def path_or_url(self, key: str) -> str:
        """Return a local path (v1) or URL (future cloud backends) for server-side use only; do not expose to clients."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if a file exists at key."""
