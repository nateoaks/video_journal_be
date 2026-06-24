"""API router for the compilations domain."""

import asyncio
import dataclasses
import json
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import SessionDep
from app.common.media_response import CACHE_IMMUTABLE, build_media_response
from app.domains.compilations import progress
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


@router.delete("/{compilation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compilation(
    compilation_id: UUID,
    service: CompilationServiceDep,
) -> None:
    """Delete a compilation and its output file.

    Returns 204 on success, 404 if not found, 409 if the compilation is running.
    """
    await service.delete(compilation_id)


@router.get("/{compilation_id}")
async def get_compilation(
    compilation_id: UUID, service: CompilationServiceDep
) -> CompilationRead:
    compilation = await service.get(compilation_id)
    return CompilationRead.model_validate(compilation)


@router.get("/{compilation_id}/video")
async def get_compilation_video(
    compilation_id: UUID, request: Request, service: CompilationServiceDep
) -> Response:
    """Stream the rendered MP4 for a complete compilation with Range/206 support.

    Raises 404 via the global exception handler if the compilation is not complete.
    """
    path = await service.open_output(compilation_id)
    return await build_media_response(
        str(path), "video/mp4", request, cache_control=CACHE_IMMUTABLE
    )


@router.get("/{compilation_id}/events")
async def get_compilation_events(
    compilation_id: UUID, request: Request, service: CompilationServiceDep
) -> StreamingResponse:
    """Stream Server-Sent Events for a compilation's render progress.

    Yields one SSE data frame per progress tick and a terminal frame when the
    render completes or fails.  Late-connecting clients receive the terminal
    state immediately if the render already finished.

    Detects client disconnection via asyncio.wait_for with a 1-second timeout
    on each queue.get(), checking is_disconnected() on timeout. Calls
    progress.unsubscribe() in the finally block only if the client disconnects
    (not when the render finishes normally, to preserve the terminal state for
    late arrivals).

    Response headers disable proxy/CDN buffering to ensure real-time delivery.
    """
    # Verify the compilation exists (raises NotFoundError → 404 if not).
    await service.get(compilation_id)

    async def _generate() -> AsyncGenerator[str]:
        # If the render already finished, emit the terminal event and close.
        terminal = progress.get_terminal(compilation_id)
        if terminal is not None:
            yield f"data: {json.dumps(dataclasses.asdict(terminal))}\n\n"
            return

        queue = progress.subscribe(compilation_id)
        if queue is None:
            # Render not yet registered (still pending).
            yield 'data: {"progress": 0, "status": "pending"}\n\n'
            return

        disconnected = False
        try:
            while True:
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    if await request.is_disconnected():
                        disconnected = True
                        break
                    continue
                yield f"data: {json.dumps(dataclasses.asdict(update))}\n\n"
                if update.status in ("complete", "failed"):
                    break
        finally:
            if disconnected:
                progress.unsubscribe(compilation_id)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
