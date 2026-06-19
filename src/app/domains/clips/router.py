from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import SessionDep
from app.domains.clips.dependencies import ClipServiceDep, get_background_clip_service
from app.domains.clips.schemas import ClipRead, ClipUpdate

router = APIRouter(prefix="/clips", tags=["clips"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_clip(
    file: Annotated[UploadFile, File(...)],
    service: ClipServiceDep,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> ClipRead:
    clip = await service.create_from_upload(file)
    # Commit before the background task is scheduled: FastAPI runs BackgroundTasks
    # after the response is sent but before generator-dependency teardown, so
    # get_session hasn't committed yet when the task's own session tries to SELECT
    # the clip. Committing here makes the row visible. The dependency's later
    # commit is a no-op.
    await session.commit()

    clip_id = clip.id

    async def _run_normalization() -> None:
        svc = await get_background_clip_service()
        session = svc.repository.session
        try:
            await svc.process_clip(clip_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    background_tasks.add_task(_run_normalization)
    return ClipRead.model_validate(clip)


@router.get("")
async def list_clips(
    service: ClipServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: int = 0,
) -> list[ClipRead]:
    clips = await service.list(limit=limit, offset=offset)
    return [ClipRead.model_validate(c) for c in clips]


@router.get("/{clip_id}")
async def get_clip(clip_id: UUID, service: ClipServiceDep) -> ClipRead:
    clip = await service.get(clip_id)
    return ClipRead.model_validate(clip)


@router.patch("/{clip_id}")
async def update_clip(
    clip_id: UUID,
    data: ClipUpdate,
    service: ClipServiceDep,
) -> ClipRead:
    clip = await service.update(clip_id, data)
    return ClipRead.model_validate(clip)


@router.delete("/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(clip_id: UUID, service: ClipServiceDep) -> None:
    await service.delete(clip_id)


@router.get("/{clip_id}/video")
async def get_clip_video(clip_id: UUID, service: ClipServiceDep) -> FileResponse:
    """Stream the normalised MP4 for a ready clip.

    Starlette's FileResponse handles HTTP Range / 206 Partial Content natively.
    Raises 404 via the global exception handler if the clip is not ready.
    """
    path = await service.open_normalized(clip_id)
    return FileResponse(str(path), media_type="video/mp4")


@router.get("/{clip_id}/filmstrip")
async def get_clip_filmstrip(clip_id: UUID, service: ClipServiceDep) -> FileResponse:
    """Return the filmstrip sprite JPEG for a ready clip.

    Raises 404 via the global exception handler if the clip is not ready or
    filmstrip generation failed during processing.
    """
    path = await service.open_filmstrip(clip_id)
    return FileResponse(str(path), media_type="image/jpeg")
