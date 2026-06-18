"""API router for the soundtracks domain."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import UUID

import anyio
import anyio.to_thread
from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.domains.soundtracks.dependencies import SoundtrackServiceDep
from app.domains.soundtracks.schemas import SoundtrackRead
from app.domains.soundtracks.utils import CONTENT_TYPES, parse_range_header
from app.storage.dependencies import StorageDep

router = APIRouter(prefix="/soundtracks", tags=["soundtracks"])

_STREAM_CHUNK_SIZE = 64 * 1024  # 64 KiB


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
    file_size = await anyio.to_thread.run_sync(lambda: Path(local_path).stat().st_size)
    content_type = CONTENT_TYPES.get(Path(key).suffix.lower(), "audio/octet-stream")
    range_header = request.headers.get("range")
    byte_range = parse_range_header(range_header, file_size)

    async def stream_full() -> AsyncIterator[bytes]:
        async with await anyio.open_file(local_path, "rb") as f:
            while chunk := await f.read(_STREAM_CHUNK_SIZE):
                yield chunk

    async def stream_range(start: int, end: int) -> AsyncIterator[bytes]:
        async with await anyio.open_file(local_path, "rb") as f:
            await f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = await f.read(min(_STREAM_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    if byte_range is None:
        return StreamingResponse(
            stream_full(),
            status_code=200,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Type": content_type,
            },
        )

    start, end = byte_range
    content_length = end - start + 1
    return StreamingResponse(
        stream_range(start, end),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
        },
    )
