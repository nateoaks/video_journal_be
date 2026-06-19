"""Data-access layer for the compilations domain."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from app.common.repository import BaseRepository
from app.domains.clips.models import Clip, ClipStatus
from app.domains.compilations.models import (
    Compilation,
    CompilationClip,
    CompilationStatus,
)
from app.domains.soundtracks.models import Soundtrack


class CompilationRepository(BaseRepository[Compilation]):
    """Data-access layer for Compilation entities."""

    model = Compilation

    async def list_recent(
        self, limit: int = 50, offset: int = 0
    ) -> Sequence[Compilation]:
        """Return compilations ordered by created_at descending."""
        result = await self.session.execute(
            select(Compilation)
            .options(selectinload(Compilation.clips))
            .order_by(Compilation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_with_clips(self, compilation_id: UUID) -> Compilation | None:
        """Return a compilation with its clips eagerly loaded, or None."""
        result = await self.session.execute(
            select(Compilation)
            .options(selectinload(Compilation.clips))
            .where(Compilation.id == compilation_id)
        )
        return result.scalar_one_or_none()

    async def running_exists(self) -> bool:
        """Return True if any compilation is currently in the running state."""
        result = await self.session.execute(
            select(exists().where(Compilation.status == CompilationStatus.running))
        )
        return bool(result.scalar())

    async def get_ready_clips(self) -> Sequence[Clip]:
        """Return clips in the ready state, ordered by sort_index (capped at 500)."""
        result = await self.session.execute(
            select(Clip)
            .where(Clip.status == ClipStatus.ready)
            .order_by(Clip.sort_index)
            .limit(500)
        )
        return result.scalars().all()

    async def get_clips_by_ids(self, clip_ids: list[UUID]) -> dict[UUID, Clip]:
        """Return a mapping of clip_id → Clip for the given IDs in one query."""
        result = await self.session.execute(select(Clip).where(Clip.id.in_(clip_ids)))
        clips = result.scalars().all()
        return {c.id: c for c in clips}

    async def get_soundtrack(self, soundtrack_id: UUID) -> Soundtrack | None:
        """Return a soundtrack by ID, or None if not found."""
        return await self.session.get(Soundtrack, soundtrack_id)

    async def add_compilation_clip(
        self, compilation_clip: CompilationClip
    ) -> CompilationClip:
        """Persist a compilation clip snapshot."""
        self.session.add(compilation_clip)
        await self.session.flush()
        return compilation_clip
