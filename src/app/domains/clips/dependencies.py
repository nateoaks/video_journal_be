from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.db.session import get_sessionmaker
from app.domains.clips.repository import ClipRepository
from app.domains.clips.service import ClipService
from app.storage import get_storage
from app.storage.dependencies import StorageDep


def get_clip_service(session: SessionDep, storage: StorageDep) -> ClipService:
    return ClipService(ClipRepository(session), storage)


ClipServiceDep = Annotated[ClipService, Depends(get_clip_service)]


async def get_background_clip_service() -> ClipService:
    """Build a ClipService with its own session for use inside background tasks.

    The caller is responsible for managing the full session lifecycle
    (open → work → commit/rollback → close).  This function is NOT a FastAPI
    Depends — call it directly inside the background task closure.
    """
    session = get_sessionmaker()()
    storage = get_storage()
    return ClipService(ClipRepository(session), storage)
