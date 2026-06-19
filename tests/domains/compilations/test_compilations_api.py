"""Integration tests for the compilations API endpoints."""

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
from app.domains.clips.models import Clip, ClipStatus
from app.domains.compilations.models import (
    Compilation,
    CompilationClip,
    CompilationStatus,
)
from app.domains.compilations.repository import CompilationRepository
from app.domains.compilations.service import CompilationService
from app.domains.soundtracks.models import Soundtrack
from app.main import create_app
from app.media.ffmpeg import FfmpegError
from app.storage import get_storage
from app.storage.local import LocalStorage

# Minimal binary payload — content doesn't matter; FFmpeg is always stubbed.
_FAKE_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"


# ---------------------------------------------------------------------------
# test_env fixture — isolated DB + wired background service + own client
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_env(tmp_path: Path) -> AsyncGenerator[dict[str, Any]]:
    """Yield {client, storage, factory, engine} with all overrides wired."""
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
            "storage": storage,
            "factory": factory,
            "engine": engine,
        }

    compilations_router_module.get_background_compilation_service = original_bg_svc  # type: ignore[assignment]
    await engine.dispose()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_ready_clip(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
    sort_index: float = 1000.0,
) -> UUID:
    """Insert a ready clip row with a fake normalised file."""
    key = f"clips/normalized/{uuid4()}.mp4"
    full_path = Path(storage.path_or_url(key))
    await anyio.to_thread.run_sync(
        lambda: (
            full_path.parent.mkdir(parents=True, exist_ok=True),
            full_path.write_bytes(_FAKE_MP4),
        )
    )

    clip = Clip(
        original_key=f"clips/original/{uuid4()}.mp4",
        normalized_key=key,
        status=ClipStatus.ready,
        sort_index=sort_index,
        trim_in_s=0.0,
        trim_out_s=5.0,
    )
    async with factory() as session:
        session.add(clip)
        await session.commit()
    return clip.id


async def _seed_soundtrack(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Insert a soundtrack row with a fake audio file."""
    key = f"soundtracks/{uuid4()}.mp3"
    full_path = Path(storage.path_or_url(key))
    await anyio.to_thread.run_sync(
        lambda: (
            full_path.parent.mkdir(parents=True, exist_ok=True),
            full_path.write_bytes(b"audio"),
        )
    )

    soundtrack = Soundtrack(key=key, title="Test Track", duration_s=30.0)
    async with factory() as session:
        session.add(soundtrack)
        await session.commit()
    return soundtrack.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_create_compilation_202_pending_with_snapshot(
    test_env: dict[str, Any],
) -> None:
    """POST creates a pending compilation with snapshot rows and returns 202."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    clip_ids = [
        await _seed_ready_clip(storage, factory, sort_index=float(i * 1000))
        for i in range(1, 4)
    ]
    soundtrack_id = await _seed_soundtrack(storage, factory)

    # Stub the render so the background task is a no-op.
    async def _stub_render(self: CompilationService, compilation_id: UUID) -> None:
        return

    original_run = CompilationService.run_compilation
    CompilationService.run_compilation = _stub_render  # type: ignore[method-assign]

    try:
        resp = await client.post(
            "/api/v1/compilations",
            json={"soundtrack_id": str(soundtrack_id)},
        )
    finally:
        CompilationService.run_compilation = original_run  # type: ignore[method-assign]

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["soundtrack_id"] == str(soundtrack_id)
    assert len(body["clips"]) == 3

    returned_clips = sorted(body["clips"], key=lambda c: c["position"])
    assert [UUID(c["clip_id"]) for c in returned_clips] == clip_ids

    for c in returned_clips:
        assert c["trim_in_s"] == 0.0
        assert c["trim_out_s"] == 5.0


async def test_create_compilation_409_when_running(
    test_env: dict[str, Any],
) -> None:
    """POST returns 409 if a compilation is already running."""
    client: AsyncClient = test_env["client"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    async with factory() as session:
        running = Compilation(status=CompilationStatus.running)
        session.add(running)
        await session.commit()

    # soundtrack_id is required; the running check fires first so any UUID works.
    resp = await client.post(
        "/api/v1/compilations", json={"soundtrack_id": str(uuid4())}
    )
    assert resp.status_code == 409


async def test_create_compilation_409_no_ready_clips(
    test_env: dict[str, Any],
) -> None:
    """POST returns 409 when there are no ready clips."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    # soundtrack_id is now required and validated before the clips check.
    soundtrack_id = await _seed_soundtrack(storage, factory)
    resp = await client.post(
        "/api/v1/compilations", json={"soundtrack_id": str(soundtrack_id)}
    )
    assert resp.status_code == 409


async def test_create_compilation_404_invalid_soundtrack(
    test_env: dict[str, Any],
) -> None:
    """POST returns 404 when the soundtrack_id doesn't exist."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    await _seed_ready_clip(storage, factory)

    resp = await client.post(
        "/api/v1/compilations",
        json={"soundtrack_id": str(uuid4())},
    )
    assert resp.status_code == 404


async def test_get_compilation_video_after_success(
    test_env: dict[str, Any],
) -> None:
    """GET /{id}/video returns 200 video/mp4 after a successful render."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    soundtrack_id = await _seed_soundtrack(storage, factory)

    output_key = f"outputs/{uuid4()}.mp4"
    output_path = Path(storage.path_or_url(output_key))
    await anyio.to_thread.run_sync(
        lambda: (
            output_path.parent.mkdir(parents=True, exist_ok=True),
            output_path.write_bytes(_FAKE_MP4),
        )
    )

    async with factory() as session:
        compilation = Compilation(
            status=CompilationStatus.complete,
            soundtrack_id=soundtrack_id,
            output_key=output_key,
        )
        session.add(compilation)
        await session.commit()
        compilation_id = compilation.id

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/video")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("video/mp4")


async def test_get_compilation_video_range(
    test_env: dict[str, Any],
) -> None:
    """Range request on /{id}/video returns 206."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    soundtrack_id = await _seed_soundtrack(storage, factory)
    output_key = f"outputs/{uuid4()}.mp4"
    output_path = Path(storage.path_or_url(output_key))
    big_payload = _FAKE_MP4 * 100
    await anyio.to_thread.run_sync(
        lambda: (
            output_path.parent.mkdir(parents=True, exist_ok=True),
            output_path.write_bytes(big_payload),
        )
    )

    async with factory() as session:
        compilation = Compilation(
            status=CompilationStatus.complete,
            soundtrack_id=soundtrack_id,
            output_key=output_key,
        )
        session.add(compilation)
        await session.commit()
        compilation_id = compilation.id

    resp = await client.get(
        f"/api/v1/compilations/{compilation_id}/video",
        headers={"Range": "bytes=0-9"},
    )
    assert resp.status_code == 206


async def test_get_compilation_video_not_complete_returns_404(
    test_env: dict[str, Any],
) -> None:
    """GET /{id}/video returns 404 when the compilation is not complete."""
    client: AsyncClient = test_env["client"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    async with factory() as session:
        compilation = Compilation(
            status=CompilationStatus.failed,
            error="ffmpeg died",
        )
        session.add(compilation)
        await session.commit()
        compilation_id = compilation.id

    resp = await client.get(f"/api/v1/compilations/{compilation_id}/video")
    assert resp.status_code == 404


async def test_render_failure_marks_compilation_failed(
    test_env: dict[str, Any],
) -> None:
    """When run_compilation encounters FfmpegError the status becomes failed."""
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    clip_key = f"clips/normalized/{uuid4()}.mp4"
    clip_path = Path(storage.path_or_url(clip_key))
    await anyio.to_thread.run_sync(
        lambda: (
            clip_path.parent.mkdir(parents=True, exist_ok=True),
            clip_path.write_bytes(_FAKE_MP4),
        )
    )

    soundtrack_key = f"soundtracks/{uuid4()}.mp3"
    st_path = Path(storage.path_or_url(soundtrack_key))
    await anyio.to_thread.run_sync(
        lambda: (
            st_path.parent.mkdir(parents=True, exist_ok=True),
            st_path.write_bytes(b"audio"),
        )
    )

    async with factory() as session:
        clip = Clip(
            original_key=f"clips/original/{uuid4()}.mp4",
            normalized_key=clip_key,
            status=ClipStatus.ready,
            sort_index=1000.0,
            trim_in_s=0.0,
            trim_out_s=5.0,
        )
        soundtrack = Soundtrack(key=soundtrack_key, title="T", duration_s=30.0)
        session.add(clip)
        session.add(soundtrack)
        await session.commit()

        compilation = Compilation(
            status=CompilationStatus.pending,
            soundtrack_id=soundtrack.id,
        )
        session.add(compilation)
        await session.commit()

        snapshot = CompilationClip(
            compilation_id=compilation.id,
            clip_id=clip.id,
            position=0,
            trim_in_s=0.0,
            trim_out_s=5.0,
        )
        session.add(snapshot)
        await session.commit()
        compilation_id = compilation.id

    import app.domains.compilations.service as svc_module

    original_compile = svc_module.compile_video

    async def _fail_compile(*args: object, **kwargs: object) -> None:
        raise FfmpegError("stderr tail here")

    svc_module.compile_video = _fail_compile  # type: ignore[assignment]

    try:
        async with factory() as session:
            svc = CompilationService(CompilationRepository(session), storage)
            await svc.run_compilation(compilation_id)
    finally:
        svc_module.compile_video = original_compile  # type: ignore[assignment]

    async with factory() as session:
        result = await session.get(Compilation, compilation_id)
        assert result is not None
        assert result.status == CompilationStatus.failed
        assert result.error == "Compilation render failed"


async def test_snapshot_immutability(
    test_env: dict[str, Any],
) -> None:
    """Changing clip trims after compile does not alter snapshot rows."""
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    async with factory() as session:
        clip = Clip(
            original_key="raw/clip.mov",
            trim_in_s=1.0,
            trim_out_s=6.0,
            status=ClipStatus.ready,
            sort_index=1000.0,
        )
        session.add(clip)
        await session.commit()

        compilation = Compilation(status=CompilationStatus.pending)
        session.add(compilation)
        await session.commit()

        snapshot = CompilationClip(
            compilation_id=compilation.id,
            clip_id=clip.id,
            position=0,
            trim_in_s=clip.trim_in_s,
            trim_out_s=clip.trim_out_s,
        )
        session.add(snapshot)
        await session.commit()

        clip.trim_in_s = 3.0
        clip.trim_out_s = 8.0
        await session.commit()

        await session.refresh(snapshot)
        assert snapshot.trim_in_s == 1.0
        assert snapshot.trim_out_s == 6.0
