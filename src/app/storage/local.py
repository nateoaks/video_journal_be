import builtins
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

import anyio
import anyio.to_thread

from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """StorageBackend that maps keys to a local filesystem directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.resolve()

    def _resolve(self, key: str) -> Path:
        """Resolve key to an absolute path, rejecting path-traversal attempts."""
        if Path(key).is_absolute():
            raise ValueError(f"Storage key must be relative, got: {key!r}")
        resolved = (self._base_dir / key).resolve()
        if not resolved.is_relative_to(self._base_dir):
            raise ValueError(f"Storage key escapes base directory: {key!r}")
        return resolved

    async def save(self, stream: AsyncIterator[bytes], key: str) -> str:
        dest = self._resolve(key)
        await anyio.to_thread.run_sync(
            lambda: dest.parent.mkdir(parents=True, exist_ok=True)
        )
        async with await anyio.open_file(dest, "wb") as f:
            async for chunk in stream:
                await f.write(chunk)
        return key

    async def open(self, key: str) -> BinaryIO:
        path = self._resolve(key)
        return await anyio.to_thread.run_sync(lambda: builtins.open(path, "rb"))

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await anyio.to_thread.run_sync(lambda: path.unlink(missing_ok=True))

    def path_or_url(self, key: str) -> str:
        return str(self._resolve(key))

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await anyio.to_thread.run_sync(path.exists)
