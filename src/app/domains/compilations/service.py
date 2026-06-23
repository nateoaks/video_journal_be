"""Business logic for the compilations domain."""

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import anyio

from app.common.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domains.clips.models import Clip
from app.domains.compilations.models import (
    Compilation,
    CompilationClip,
    CompilationStatus,
)
from app.domains.compilations.progress import ProgressUpdate
from app.domains.compilations.progress import finalize as _finalize
from app.domains.compilations.progress import push_from_thread as _push
from app.domains.compilations.progress import register as _register
from app.domains.compilations.repository import CompilationRepository
from app.domains.compilations.schemas import CompilationCreate
from app.domains.compilations.utils import build_output_key, truncate_stderr
from app.media.compile import ClipSpec, compile_video
from app.media.ffmpeg import FfmpegError
from app.media.ffprobe import FfprobeError, probe
from app.storage.base import StorageBackend

logger = get_logger(__name__)


class CompilationService:
    """Orchestrates compilation creation and rendering."""

    def __init__(
        self, repository: CompilationRepository, storage: StorageBackend
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def create(self, data: CompilationCreate) -> Compilation:
        """Validate inputs, create a pending compilation, and snapshot timeline.

        Does NOT start the render — the caller (router) enqueues the background
        task after committing.
        """
        await self._check_no_running_compilation()
        await self._validate_soundtrack(data.soundtrack_id)
        ready_clips = await self._get_ready_clips()

        compilation = Compilation(
            id=uuid.uuid4(),
            soundtrack_id=data.soundtrack_id,
            status=CompilationStatus.pending,
        )
        await self.repository.add(compilation)

        snapshots: list[CompilationClip] = []
        for position, clip in enumerate(ready_clips):
            snapshot = CompilationClip(
                compilation_id=compilation.id,
                clip_id=clip.id,
                position=position,
                trim_in_s=clip.trim_in_s,
                trim_out_s=clip.trim_out_s,
            )
            await self.repository.add_compilation_clip(snapshot)
            snapshots.append(snapshot)

        # Populate the relationship in-memory so the router can serialise it
        # without a second DB round-trip (selectinload after expire causes
        # greenlet issues in async context).
        compilation.clips = snapshots
        return compilation

    async def get(self, compilation_id: UUID) -> Compilation:
        """Return a compilation (with clips) by ID, raising NotFoundError if absent."""
        compilation = await self.repository.get_with_clips(compilation_id)
        if compilation is None:
            raise NotFoundError(f"Compilation {compilation_id} not found")
        return compilation

    async def list_compilations(
        self, limit: int = 50, offset: int = 0
    ) -> list[Compilation]:
        """Return compilations ordered by created_at descending."""
        results = await self.repository.list_recent(limit=limit, offset=offset)
        return list(results)

    async def open_output(self, compilation_id: UUID) -> Path:
        """Return the local filesystem path to the rendered MP4.

        Raises NotFoundError if the compilation is not complete or has no output.
        """
        compilation = await self.repository.get(compilation_id)
        if compilation is None:
            raise NotFoundError(f"Compilation {compilation_id} not found")
        if (
            compilation.status != CompilationStatus.complete
            or compilation.output_key is None
        ):
            raise NotFoundError(f"Compilation {compilation_id} output is not available")
        return Path(self.storage.path_or_url(compilation.output_key))

    async def run_compilation(self, compilation_id: UUID) -> None:
        """Render the compilation in the background.

        Designed to run inside a background task with its own session.
        On FfmpegError the compilation is marked failed with the FFmpeg stderr
        tail (truncated to 2000 characters for safety) and finalized; the
        exception is NOT re-raised so the background task exits cleanly.
        The temp file is always removed in the finally block.
        """
        compilation = await self.repository.get_with_clips(compilation_id)
        if compilation is None:
            logger.error(
                "compilation.render.not_found", compilation_id=str(compilation_id)
            )
            return

        _register(compilation_id)

        compilation.status = CompilationStatus.running
        await self.repository.add(compilation)
        await self.repository.session.commit()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as _tmp:
            dst_path = _tmp.name

        try:
            clip_specs = await self._build_clip_specs(compilation)
            soundtrack_path = await self._resolve_soundtrack_path(compilation)
            total_duration = sum(
                spec.trim_out_s - spec.trim_in_s for spec in clip_specs
            )

            total_us = total_duration * 1_000_000

            def _on_progress(out_time_us: int) -> None:
                pct = min(100, int(out_time_us / total_us * 100)) if total_us > 0 else 0
                _push(compilation_id, ProgressUpdate(progress=pct, status="running"))

            await compile_video(
                clip_specs,
                soundtrack_path,
                dst_path,
                total_duration,
                on_progress=_on_progress,
            )

            output_key = build_output_key(compilation.id)

            async def _file_stream() -> AsyncIterator[bytes]:
                async with await anyio.open_file(dst_path, "rb") as fh:
                    while True:
                        chunk = await fh.read(1024 * 1024)
                        if not chunk:
                            break
                        yield chunk

            await self.storage.save(_file_stream(), output_key)

            try:
                probe_result = await probe(dst_path)
                compilation.duration_s = probe_result.duration_s
            except FfprobeError as exc:
                logger.warning(
                    "compilation.duration.probe_failed",
                    compilation_id=str(compilation.id),
                    error=str(exc),
                )

            compilation.output_key = output_key
            compilation.status = CompilationStatus.complete
            compilation.completed_at = datetime.now(UTC)
            await self.repository.add(compilation)
            await self.repository.session.commit()

            _finalize(
                compilation_id,
                ProgressUpdate(
                    progress=100,
                    status="complete",
                    video_url=f"/api/v1/compilations/{compilation_id}/video",
                ),
            )
            logger.info(
                "compilation.render.complete",
                compilation_id=str(compilation_id),
                output_key=output_key,
            )

        except FfmpegError as exc:
            stderr_tail = truncate_stderr(exc.message)
            _finalize(
                compilation_id,
                ProgressUpdate(progress=0, status="failed", error=stderr_tail),
            )
            await self.repository.session.rollback()
            compilation = await self.repository.get(compilation_id)
            if compilation is not None:
                compilation.status = CompilationStatus.failed
                compilation.error = stderr_tail
                compilation.completed_at = datetime.now(UTC)
                await self.repository.add(compilation)
                await self.repository.session.commit()
            logger.error(
                "compilation.render.failed",
                compilation_id=str(compilation_id),
                stderr=str(exc),
            )

        except Exception:
            _finalize(
                compilation_id,
                ProgressUpdate(
                    progress=0, status="failed", error="Unexpected render error"
                ),
            )
            await self.repository.session.rollback()
            compilation = await self.repository.get(compilation_id)
            if compilation is not None:
                compilation.status = CompilationStatus.failed
                compilation.error = "Unexpected render error"
                compilation.completed_at = datetime.now(UTC)
                await self.repository.add(compilation)
                await self.repository.session.commit()
            logger.exception(
                "compilation.render.unexpected_error",
                compilation_id=str(compilation_id),
            )

        finally:
            await anyio.to_thread.run_sync(
                lambda: Path(dst_path).unlink(missing_ok=True)
            )

    # --- private helpers ---

    async def _check_no_running_compilation(self) -> None:
        """Raise ConflictError if a compilation is already running."""
        if await self.repository.running_exists():
            raise ConflictError("A compilation is already running")

    async def _validate_soundtrack(self, soundtrack_id: UUID) -> None:
        """Raise NotFoundError if the soundtrack doesn't exist."""
        soundtrack = await self.repository.get_soundtrack(soundtrack_id)
        if soundtrack is None:
            raise NotFoundError(f"Soundtrack {soundtrack_id} not found")

    async def _get_ready_clips(self) -> list[Clip]:
        """Raise ConflictError if there are no ready clips."""
        result = await self.repository.get_ready_clips()
        clips: list[Clip] = list(result)
        if not clips:
            raise ConflictError("No ready clips available for compilation")
        return clips

    async def _build_clip_specs(self, compilation: Compilation) -> list[ClipSpec]:
        """Build the ClipSpec list from the compilation's snapshots.

        Fetches all required clips in a single batch query to avoid N+1.
        """
        sorted_ccs = sorted(compilation.clips, key=lambda c: c.position)
        clip_ids = [cc.clip_id for cc in sorted_ccs]
        clips_by_id = await self.repository.get_clips_by_ids(clip_ids)

        specs: list[ClipSpec] = []
        for cc in sorted_ccs:
            clip = clips_by_id.get(cc.clip_id)
            if clip is None or clip.normalized_key is None:
                raise NotFoundError(f"Clip {cc.clip_id} has no normalized file")
            path = self.storage.path_or_url(clip.normalized_key)
            trim_in = cc.trim_in_s if cc.trim_in_s is not None else 0.0
            # Fall back to the clip's full duration when no explicit trim-out is set.
            trim_out = (
                cc.trim_out_s if cc.trim_out_s is not None else (clip.duration_s or 0.0)
            )
            specs.append(ClipSpec(path=path, trim_in_s=trim_in, trim_out_s=trim_out))
        return specs

    async def _resolve_soundtrack_path(self, compilation: Compilation) -> str:
        """Return the storage path for the compilation's soundtrack."""
        if compilation.soundtrack_id is None:
            raise NotFoundError("Compilation has no soundtrack")
        soundtrack = await self.repository.get_soundtrack(compilation.soundtrack_id)
        if soundtrack is None:
            raise NotFoundError(f"Soundtrack {compilation.soundtrack_id} not found")
        return self.storage.path_or_url(soundtrack.key)
