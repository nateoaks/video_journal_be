from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.domains.clips.repository import ClipRepository
from app.domains.clips.service import ClipService
from app.storage.dependencies import StorageDep


def get_clip_service(session: SessionDep, storage: StorageDep) -> ClipService:
    return ClipService(ClipRepository(session), storage)


ClipServiceDep = Annotated[ClipService, Depends(get_clip_service)]
