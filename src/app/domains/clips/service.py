"""Business logic for the clips domain."""

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.common.exceptions import NotFoundError, UploadTooLargeError
from app.core.config import get_settings
from app.domains.clips.exceptions import InvalidTrimError
from app.domains.clips.models import Clip, ClipStatus
from app.domains.clips.repository import ClipRepository
from app.domains.clips.schemas import ClipUpdate
from app.domains.clips.utils import build_original_key, safe_extension
from app.media.ffprobe import FfprobeError, probe
from app.storage.base import StorageBackend

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _file_mtime(path: Path) -> datetime | None:
    """Return the file's mtime as a UTC-aware datetime, or None if unavailable."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=UTC)
    except OSError:
        return None


class ClipService:
    """Orchestrates clip upload, metadata extraction, ordering, and lifecycle."""

    def __init__(self, repository: ClipRepository, storage: StorageBackend) -> None:
        self.repository = repository
        self.storage = storage

    async def create_from_upload(self, upload: UploadFile) -> Clip:
        """Validate, store, probe, and persist a newly uploaded clip file."""
        ext = safe_extension(upload.filename)

        clip_id = uuid.uuid4()
        key = build_original_key(clip_id, ext)

        try:
            await self.storage.save(self._iter_upload(upload), key)
        except UploadTooLargeError:
            await self.storage.delete(key)
            raise

        try:
            path = self.storage.path_or_url(key)
            probe_result = await probe(path)
        except FfprobeError:
            await self.storage.delete(key)
            raise

        recorded_at = (
            probe_result.recorded_at or _file_mtime(Path(path)) or datetime.now(UTC)
        )
        sort_index = await self._assign_sort_index(recorded_at)

        clip = Clip(
            id=clip_id,
            original_key=key,
            duration_s=probe_result.duration_s,
            width=probe_result.width,
            height=probe_result.height,
            codec_name=probe_result.codec_name,
            recorded_at=recorded_at,
            trim_in_s=0.0,
            trim_out_s=probe_result.duration_s or 0.0,
            sort_index=sort_index,
            status=ClipStatus.processing,
        )
        try:
            return await self.repository.add(clip)
        except Exception:
            await self.storage.delete(key)
            raise

    async def get(self, clip_id: UUID) -> Clip:
        """Return a clip by ID, raising NotFoundError if absent."""
        clip = await self.repository.get(clip_id)
        if clip is None:
            raise NotFoundError(f"Clip {clip_id} not found")
        return clip

    async def list(self, limit: int = 50, offset: int = 0) -> Sequence[Clip]:
        """Return clips in sort_index order."""
        return await self.repository.list_ordered(limit=limit, offset=offset)

    async def update(self, clip_id: UUID, data: ClipUpdate) -> Clip:
        """Apply a partial update to a clip, enforcing trim-window validity."""
        clip = await self.get(clip_id)

        if data.trim_in_s is not None:
            clip.trim_in_s = data.trim_in_s
        if data.trim_out_s is not None:
            clip.trim_out_s = data.trim_out_s
        if data.sort_index is not None:
            clip.sort_index = data.sort_index

        self._validate_trim(clip)
        return await self.repository.add(clip)

    async def delete(self, clip_id: UUID) -> None:
        """Delete a clip record and all associated storage keys.

        Storage files are deleted before the DB row so that a commit failure
        leaves an orphaned file (recoverable by a janitor) rather than a
        missing file after DB rollback (permanent data loss).
        """
        clip = await self.get(clip_id)

        for key in (clip.original_key, clip.normalized_key, clip.filmstrip_key):
            if key is not None:
                await self.storage.delete(key)

        await self.repository.delete(clip)

    # --- private helpers ---

    async def _iter_upload(self, upload: UploadFile) -> AsyncIterator[bytes]:
        """Yield chunks from an UploadFile, 1 MiB at a time.

        Raises UploadTooLargeError when the upload exceeds
        ``Settings.max_upload_bytes``.  The caller is responsible for deleting
        any partial storage key on that error.
        """
        max_bytes = get_settings().max_upload_bytes
        total = 0
        while True:
            chunk = await upload.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise UploadTooLargeError(
                    f"Upload exceeds maximum allowed size of {max_bytes} bytes"
                )
            yield chunk

    async def _assign_sort_index(self, recorded_at: datetime) -> float:
        """Return a fractional sort_index that places a clip in chronological order."""
        max_idx = await self.repository.max_sort_index()
        if max_idx is None:
            # Table is empty.
            return 1000.0

        prev, next_ = await self.repository.neighbors_for_recorded_at(recorded_at)

        if prev is None:
            if next_ is None:
                # Clips exist but none have recorded_at — append at end.
                return (max_idx or 0.0) + 1000.0
            # New clip is earliest; insert before next_.
            return next_.sort_index - 1000.0

        if next_ is None:
            # New clip is latest; append after everything.
            return (max_idx or 0.0) + 1000.0

        # Bisect between neighbours.
        return (prev.sort_index + next_.sort_index) / 2.0

    @staticmethod
    def _validate_trim(clip: Clip) -> None:
        """Raise InvalidTrimError if the clip's trim window is logically invalid."""
        trim_in = clip.trim_in_s
        trim_out = clip.trim_out_s

        if trim_in is not None and trim_out is not None:
            if trim_in >= trim_out:
                raise InvalidTrimError("trim_in_s must be less than trim_out_s")
            if clip.duration_s is not None and trim_out > clip.duration_s:
                raise InvalidTrimError("trim_out_s cannot exceed the clip duration")
