"""API router for the compilations domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, status
from fastapi.responses import FileResponse

from app.api.deps import SessionDep
from app.domains.compilations.dependencies import (
    CompilationServiceDep,
    get_background_compilation_service,
)
from app.domains.compilations.schemas import CompilationCreate, CompilationRead

router = APIRouter(prefix="/compilations", tags=["compilations"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_compilation(
    data: CompilationCreate,
    service: CompilationServiceDep,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> CompilationRead:
    """Create a compilation from all ready clips + optional soundtrack.

    Returns 202 immediately; the render runs in a background task.
    """
    compilation = await service.create(data)
    # Commit before enqueueing so the background task's own session can see the row.
    await session.commit()

    compilation_id = compilation.id

    async def _run_render() -> None:
        svc = await get_background_compilation_service()
        bg_session = svc.repository.session
        try:
            await svc.run_compilation(compilation_id)
        finally:
            await bg_session.close()

    background_tasks.add_task(_run_render)
    return CompilationRead.model_validate(compilation)


@router.get("")
async def list_compilations(
    service: CompilationServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CompilationRead]:
    compilations = await service.list_compilations(limit=limit, offset=offset)
    return [CompilationRead.model_validate(c) for c in compilations]


@router.get("/{compilation_id}")
async def get_compilation(
    compilation_id: UUID, service: CompilationServiceDep
) -> CompilationRead:
    compilation = await service.get(compilation_id)
    return CompilationRead.model_validate(compilation)


@router.get("/{compilation_id}/video")
async def get_compilation_video(
    compilation_id: UUID, service: CompilationServiceDep
) -> FileResponse:
    """Stream the rendered MP4 for a complete compilation.

    Starlette's FileResponse handles HTTP Range / 206 Partial Content natively.
    Raises 404 via the global exception handler if the compilation is not complete.
    """
    path = await service.open_output(compilation_id)
    return FileResponse(str(path), media_type="video/mp4")
