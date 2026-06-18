from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile, status

from app.domains.clips.dependencies import ClipServiceDep
from app.domains.clips.schemas import ClipRead, ClipUpdate

router = APIRouter(prefix="/clips", tags=["clips"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_clip(
    file: Annotated[UploadFile, File(...)],
    service: ClipServiceDep,
) -> ClipRead:
    clip = await service.create_from_upload(file)
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
