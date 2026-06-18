"""Business logic for the soundtracks domain."""

import uuid
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

from fastapi import UploadFile

from app.common.exceptions import NotFoundError, UploadTooLargeError
from app.core.config import get_settings
from app.domains.soundtracks.models import Soundtrack
from app.domains.soundtracks.repository import SoundtrackRepository
from app.domains.soundtracks.utils import (
    build_soundtrack_key,
    safe_extension,
    title_from_filename,
)
from app.media.ffprobe import FfprobeError, probe_audio
from app.storage.base import StorageBackend

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class SoundtrackService:
    """Orchestrates soundtrack upload, metadata extraction, and lifecycle."""

    def __init__(
        self, repository: SoundtrackRepository, storage: StorageBackend
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def create_from_upload(self, upload: UploadFile) -> Soundtrack:
        """Validate, store, probe, and persist a newly uploaded soundtrack file."""
        ext = safe_extension(upload.filename)

        soundtrack_id = uuid.uuid4()
        key = build_soundtrack_key(soundtrack_id, ext)

        try:
            await self.storage.save(self._iter_upload(upload), key)
        except UploadTooLargeError:
            await self.storage.delete(key)
            raise

        try:
            path = self.storage.path_or_url(key)
            probe_result = await probe_audio(path)
        except FfprobeError:
            await self.storage.delete(key)
            raise

        resolved_title = probe_result.title or title_from_filename(
            upload.filename or ""
        )

        soundtrack = Soundtrack(
            id=soundtrack_id,
            key=key,
            title=resolved_title,
            duration_s=probe_result.duration_s,
        )
        try:
            return await self.repository.add(soundtrack)
        except Exception:
            await self.storage.delete(key)
            raise

    async def get(self, soundtrack_id: UUID) -> Soundtrack:
        """Return a soundtrack by ID, raising NotFoundError if absent."""
        soundtrack = await self.repository.get(soundtrack_id)
        if soundtrack is None:
            raise NotFoundError(f"Soundtrack {soundtrack_id} not found")
        return soundtrack

    async def list(self, limit: int = 50, offset: int = 0) -> Sequence[Soundtrack]:
        """Return soundtracks ordered by uploaded_at descending."""
        return await self.repository.list_recent(limit=limit, offset=offset)

    async def delete(self, soundtrack_id: UUID) -> None:
        """Delete a soundtrack record and its associated storage file.

        Storage file is deleted before the DB row so that a commit failure
        leaves an orphaned file (recoverable) rather than a missing file
        after DB rollback (permanent data loss).
        """
        soundtrack = await self.get(soundtrack_id)
        await self.storage.delete(soundtrack.key)
        await self.repository.delete(soundtrack)

    async def open_audio(self, soundtrack_id: UUID) -> tuple[Soundtrack, str]:
        """Return the soundtrack and its storage key for streaming."""
        soundtrack = await self.get(soundtrack_id)
        return soundtrack, soundtrack.key

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
