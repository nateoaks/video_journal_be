"""Data-access layer for the soundtracks domain."""

from collections.abc import Sequence

from sqlalchemy import select

from app.common.repository import BaseRepository
from app.domains.soundtracks.models import Soundtrack


class SoundtrackRepository(BaseRepository[Soundtrack]):
    """Data-access layer for Soundtrack entities."""

    model = Soundtrack

    async def list_recent(
        self, limit: int = 50, offset: int = 0
    ) -> Sequence[Soundtrack]:
        """Return soundtracks ordered by uploaded_at descending."""
        result = await self.session.execute(
            select(Soundtrack)
            .order_by(Soundtrack.uploaded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
