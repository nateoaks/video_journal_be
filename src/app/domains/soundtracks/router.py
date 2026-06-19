"""API router for the soundtracks domain."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status

from app.common.media_response import CACHE_IMMUTABLE, build_media_response
from app.domains.soundtracks.dependencies import SoundtrackServiceDep
from app.domains.soundtracks.schemas import SoundtrackRead
from app.domains.soundtracks.utils import CONTENT_TYPES
from app.storage.dependencies import StorageDep

router = APIRouter(prefix="/soundtracks", tags=["soundtracks"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_soundtrack(
    file: Annotated[UploadFile, File(...)],
    service: SoundtrackServiceDep,
) -> SoundtrackRead:
    soundtrack = await service.create_from_upload(file)
    return SoundtrackRead.model_validate(soundtrack)


@router.get("")
async def list_soundtracks(
    service: SoundtrackServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SoundtrackRead]:
    soundtracks = await service.list(limit=limit, offset=offset)
    return [SoundtrackRead.model_validate(s) for s in soundtracks]


@router.get("/{soundtrack_id}")
async def get_soundtrack(
    soundtrack_id: UUID, service: SoundtrackServiceDep
) -> SoundtrackRead:
    soundtrack = await service.get(soundtrack_id)
    return SoundtrackRead.model_validate(soundtrack)


@router.delete("/{soundtrack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_soundtrack(soundtrack_id: UUID, service: SoundtrackServiceDep) -> None:
    await service.delete(soundtrack_id)


@router.get("/{soundtrack_id}/audio")
async def stream_audio(
    soundtrack_id: UUID,
    request: Request,
    service: SoundtrackServiceDep,
    storage: StorageDep,
) -> Response:
    """Stream the audio file, supporting Range requests for browser playback."""
    _soundtrack, key = await service.open_audio(soundtrack_id)
    local_path = storage.path_or_url(key)
    content_type = CONTENT_TYPES.get(Path(key).suffix.lower(), "audio/octet-stream")
    return await build_media_response(
        local_path,
        content_type,
        request,
        cache_control=CACHE_IMMUTABLE,
    )
