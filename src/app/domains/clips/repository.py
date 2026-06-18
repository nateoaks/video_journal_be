from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.common.repository import BaseRepository
from app.domains.clips.models import Clip


class ClipRepository(BaseRepository[Clip]):
    """Data-access layer for Clip entities."""

    model = Clip

    async def list_ordered(self, limit: int = 50, offset: int = 0) -> Sequence[Clip]:
        """Return clips ordered by sort_index ascending."""
        result = await self.session.execute(
            select(Clip).order_by(Clip.sort_index).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def max_sort_index(self) -> float | None:
        """Return the highest sort_index currently in the table, or None if empty."""
        result = await self.session.execute(select(func.max(Clip.sort_index)))
        return result.scalar_one_or_none()

    async def neighbors_for_recorded_at(
        self, recorded_at: datetime
    ) -> tuple[Clip | None, Clip | None]:
        """Find the clips that would immediately precede and follow a new clip.

        prev: the clip with the largest sort_index whose recorded_at <= recorded_at.
        next_: the clip with the smallest sort_index whose recorded_at > recorded_at.
        Only considers clips that have a non-null recorded_at.
        """
        prev_result = await self.session.execute(
            select(Clip)
            .where(Clip.recorded_at.is_not(None))
            .where(Clip.recorded_at <= recorded_at)
            .order_by(Clip.recorded_at.desc())
            .limit(1)
        )
        prev = prev_result.scalar_one_or_none()

        next_result = await self.session.execute(
            select(Clip)
            .where(Clip.recorded_at.is_not(None))
            .where(Clip.recorded_at > recorded_at)
            .order_by(Clip.recorded_at.asc())
            .limit(1)
        )
        next_ = next_result.scalar_one_or_none()

        return prev, next_
