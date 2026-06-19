"""FastAPI dependency providers for the soundtracks domain."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.domains.soundtracks.repository import SoundtrackRepository
from app.domains.soundtracks.service import SoundtrackService
from app.storage.dependencies import StorageDep


def get_soundtrack_service(
    session: SessionDep, storage: StorageDep
) -> SoundtrackService:
    return SoundtrackService(SoundtrackRepository(session), storage)


SoundtrackServiceDep = Annotated[SoundtrackService, Depends(get_soundtrack_service)]
