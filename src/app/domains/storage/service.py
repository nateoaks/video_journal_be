"""Business logic for the storage domain."""

from pathlib import Path

import anyio.to_thread

from app.domains.storage.schemas import StorageUsageRead
from app.storage.base import StorageBackend

# Category → storage key prefix mapping.
_CATEGORIES: dict[str, str] = {
    "originals": "clips/original",
    "normalized": "clips/normalized",
    "filmstrips": "clips/filmstrip",
    "soundtracks": "soundtracks",
    "outputs": "outputs",
}


def _dir_size(path: Path) -> int:
    """Return the total byte size of all regular files under path.

    Returns 0 if the directory does not exist.  Only regular files are counted;
    symlinks and directories are skipped.
    """
    if not path.exists():
        return 0
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file() and not entry.is_symlink():
            total += entry.stat().st_size
    return total


class StorageUsageService:
    """Compute on-demand disk usage across all storage categories."""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    async def _size_for_prefix(self, prefix: str) -> int:
        """Return total bytes for a single category prefix, run off the event loop."""
        dir_path = Path(self.storage.path_or_url(prefix))
        return await anyio.to_thread.run_sync(lambda: _dir_size(dir_path))

    async def compute_usage(self) -> StorageUsageRead:
        """Walk each category directory off the event loop and return byte totals."""
        sizes: dict[str, int] = {}
        for category, prefix in _CATEGORIES.items():
            sizes[category] = await self._size_for_prefix(prefix)

        return StorageUsageRead(
            originals_bytes=sizes["originals"],
            normalized_bytes=sizes["normalized"],
            filmstrips_bytes=sizes["filmstrips"],
            soundtracks_bytes=sizes["soundtracks"],
            outputs_bytes=sizes["outputs"],
            total_bytes=sum(sizes.values()),
        )
