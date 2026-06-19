"""FastAPI dependency providers for the compilations domain."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.db.session import get_sessionmaker
from app.domains.compilations.repository import CompilationRepository
from app.domains.compilations.service import CompilationService
from app.storage import get_storage
from app.storage.dependencies import StorageDep


def get_compilation_service(
    session: SessionDep, storage: StorageDep
) -> CompilationService:
    return CompilationService(CompilationRepository(session), storage)


CompilationServiceDep = Annotated[CompilationService, Depends(get_compilation_service)]


async def get_background_compilation_service() -> CompilationService:
    """Build a CompilationService with its own session for use inside background tasks.

    The caller is responsible for managing the full session lifecycle
    (open → work → commit/rollback → close).  This function is NOT a FastAPI
    Depends — call it directly inside the background task closure.
    """
    session = get_sessionmaker()()
    storage = get_storage()
    return CompilationService(CompilationRepository(session), storage)
