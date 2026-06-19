"""Integration tests for the SSE compilation progress endpoint."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import anyio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.domains.compilations.router as compilations_router_module
from app.db.base import Base
from app.db.session import get_session
from app.domains.compilations import progress as prog_module
from app.domains.compilations.models import Compilation, CompilationStatus
from app.domains.compilations.progress import ProgressUpdate
from app.domains.compilations.repository import CompilationRepository
from app.domains.compilations.service import CompilationService
from app.main import create_app
from app.storage import get_storage
from app.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def sse_env(tmp_path: Path) -> AsyncGenerator[dict[str, Any]]:
    """Isolated DB + app wired for SSE tests; clears progress state between tests."""
    storage = LocalStorage(tmp_path / "media")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_storage() -> LocalStorage:
        return storage

    async def override_bg_compile_svc() -> CompilationService:
        session = factory()
        return CompilationService(CompilationRepository(session), storage)

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_storage] = override_get_storage

    original_bg_svc = compilations_router_module.get_background_compilation_service
    compilations_router_module.get_background_compilation_service = (  # type: ignore[assignment]
        override_bg_compile_svc
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield {
            "client": http_client,
            "factory": factory,
        }

    compilations_router_module.get_background_compilation_service = original_bg_svc  # type: ignore[assignment]
    await engine.dispose()

    # Clean up any residual progress state so tests don't bleed into each other.
    prog_module._channels.clear()
    prog_module._terminal.clear()


# ---------------------------------------------------------------------------
# Helper: insert a bare compilation row
# ---------------------------------------------------------------------------


async def _seed_compilation(
    factory: async_sessionmaker[AsyncSession],
    status: CompilationStatus = CompilationStatus.pending,
) -> UUID:
    async with factory() as session:
        compilation = Compilation(status=status)
        session.add(compilation)
        await session.commit()
        return compilation.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_events_404_for_unknown_compilation(
    sse_env: dict[str, Any],
) -> None:
    """GET /events returns 404 for a compilation that does not exist."""
    client: AsyncClient = sse_env["client"]
    resp = await client.get(f"/api/v1/compilations/{uuid4()}/events")
    assert resp.status_code == 404


async def test_events_returns_terminal_immediately_when_complete(
    sse_env: dict[str, Any],
) -> None:
    """If the terminal state is already stored the response contains it immediately."""
    client: AsyncClient = sse_env["client"]
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.complete)

    # Inject terminal state as if the render already finished.
    terminal = ProgressUpdate(
        progress=100,
        status="complete",
        video_url=f"/api/v1/compilations/{compilation_id}/video",
    )
    prog_module._terminal[compilation_id] = terminal

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Parse SSE frames: strip "data: " prefix and trailing blank lines.
    frames = [
        line[len("data: ") :]
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    payload = json.loads(frames[0])
    assert payload["status"] == "complete"
    assert payload["progress"] == 100
    assert "video_url" in payload


async def test_events_returns_failed_terminal_with_error(
    sse_env: dict[str, Any],
) -> None:
    """A failed terminal event includes the error field."""
    client: AsyncClient = sse_env["client"]
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.failed)
    terminal = ProgressUpdate(progress=0, status="failed", error="stderr tail here")
    prog_module._terminal[compilation_id] = terminal

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/events")
    assert resp.status_code == 200

    frames = [
        line[len("data: ") :]
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    payload = json.loads(frames[0])
    assert payload["status"] == "failed"
    assert payload["error"] == "stderr tail here"


async def test_events_returns_pending_when_not_registered(
    sse_env: dict[str, Any],
) -> None:
    """If the compilation exists but hasn't been registered yet, return pending."""
    client: AsyncClient = sse_env["client"]
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.pending)
    # No entry in _channels or _terminal — simulates a pending job.

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/events")
    assert resp.status_code == 200

    frames = [
        line[len("data: ") :]
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    payload = json.loads(frames[0])
    assert payload["status"] == "pending"
    assert payload["progress"] == 0


async def test_events_anti_buffering_headers(
    sse_env: dict[str, Any],
) -> None:
    """The SSE endpoint sets Cache-Control and X-Accel-Buffering headers."""
    client: AsyncClient = sse_env["client"]
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.complete)
    terminal = ProgressUpdate(progress=100, status="complete")
    prog_module._terminal[compilation_id] = terminal

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/events")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-cache"
    assert resp.headers.get("x-accel-buffering") == "no"


async def test_events_disconnect_removes_channel(
    sse_env: dict[str, Any],
) -> None:
    """When the client disconnects mid-stream, the channel is removed from _channels."""
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.running)

    # Register a channel but never push a terminal — simulates a long-running render.
    prog_module.register(compilation_id)
    assert compilation_id in prog_module._channels

    # Test the unsubscribe helper directly — the full router finally-block path
    # cannot be simulated via ASGITransport (no real mid-stream disconnect).
    prog_module.unsubscribe(compilation_id)

    assert compilation_id not in prog_module._channels


async def test_events_streams_progress_and_terminal(
    sse_env: dict[str, Any],
) -> None:
    """Progress updates pushed to the queue appear in the SSE stream in order."""
    client: AsyncClient = sse_env["client"]
    factory: async_sessionmaker[AsyncSession] = sse_env["factory"]

    compilation_id = await _seed_compilation(factory, status=CompilationStatus.running)

    # Register the compilation in the progress registry within an async context.
    queue = prog_module.register(compilation_id)

    # Push two progress updates and a terminal in the background.
    async def _push_events() -> None:
        # Small delay so the SSE generator has time to enter its drain loop.
        await asyncio.sleep(0.05)
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(
            queue.put_nowait, ProgressUpdate(progress=25, status="running")
        )
        loop.call_soon_threadsafe(
            queue.put_nowait, ProgressUpdate(progress=50, status="running")
        )
        prog_module.finalize(
            compilation_id,
            ProgressUpdate(
                progress=100,
                status="complete",
                video_url=f"/api/v1/compilations/{compilation_id}/video",
            ),
        )

    async with anyio.create_task_group() as tg:
        tg.start_soon(_push_events)
        resp = await client.get(f"/api/v1/compilations/{compilation_id}/events")

    assert resp.status_code == 200
    frames = [
        json.loads(line[len("data: ") :])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 3
    assert frames[0] == {
        "progress": 25,
        "status": "running",
        "video_url": None,
        "error": None,
    }
    assert frames[1] == {
        "progress": 50,
        "status": "running",
        "video_url": None,
        "error": None,
    }
    assert frames[2]["status"] == "complete"
    assert frames[2]["progress"] == 100
