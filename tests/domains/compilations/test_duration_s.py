"""Tests for duration_s storage on compilation records."""

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
import app.domains.compilations.service as svc_module
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
from app.media.ffprobe import FfprobeError, ProbeResult
from app.storage import get_storage
from app.storage.local import LocalStorage

_FAKE_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"


# ---------------------------------------------------------------------------
# Shared fixture (same pattern as test_compilations_api.py)
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


async def _seed_compilation_with_clip_and_soundtrack(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Seed a pending compilation with one clip snapshot and a soundtrack."""
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
        return compilation.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_compilation_sets_duration_s_on_success(
    test_env: dict[str, Any],
) -> None:
    """run_compilation stores duration_s from probe on a successful render."""
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    compilation_id = await _seed_compilation_with_clip_and_soundtrack(storage, factory)

    original_compile = svc_module.compile_video
    original_probe = svc_module.probe

    async def _noop_compile(*args: object, **kwargs: object) -> None:
        return

    async def _fake_probe(path: object) -> ProbeResult:
        return ProbeResult(
            duration_s=42.5,
            width=1920,
            height=1080,
            codec_name="h264",
            recorded_at=None,
        )

    svc_module.compile_video = _noop_compile  # type: ignore[assignment]
    svc_module.probe = _fake_probe  # type: ignore[assignment]

    try:
        async with factory() as session:
            svc = CompilationService(CompilationRepository(session), storage)
            await svc.run_compilation(compilation_id)
    finally:
        svc_module.compile_video = original_compile  # type: ignore[assignment]
        svc_module.probe = original_probe  # type: ignore[assignment]

    async with factory() as session:
        result = await session.get(Compilation, compilation_id)
        assert result is not None
        assert result.status == CompilationStatus.complete
        assert result.duration_s == 42.5


async def test_run_compilation_duration_s_none_on_probe_failure(
    test_env: dict[str, Any],
) -> None:
    """Probe failure leaves duration_s as None but render still completes."""
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    compilation_id = await _seed_compilation_with_clip_and_soundtrack(storage, factory)

    original_compile = svc_module.compile_video
    original_probe = svc_module.probe

    async def _noop_compile(*args: object, **kwargs: object) -> None:
        return

    async def _failing_probe(path: object) -> ProbeResult:
        raise FfprobeError("ffprobe unavailable")

    svc_module.compile_video = _noop_compile  # type: ignore[assignment]
    svc_module.probe = _failing_probe  # type: ignore[assignment]

    try:
        async with factory() as session:
            svc = CompilationService(CompilationRepository(session), storage)
            await svc.run_compilation(compilation_id)
    finally:
        svc_module.compile_video = original_compile  # type: ignore[assignment]
        svc_module.probe = original_probe  # type: ignore[assignment]

    async with factory() as session:
        result = await session.get(Compilation, compilation_id)
        assert result is not None
        assert result.status == CompilationStatus.complete
        assert result.output_key is not None
        assert result.duration_s is None


async def test_get_compilation_duration_s_in_api_response(
    test_env: dict[str, Any],
) -> None:
    """GET /compilations/{id} returns duration_s as a float when set."""
    client: AsyncClient = test_env["client"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    async with factory() as session:
        compilation = Compilation(
            status=CompilationStatus.complete,
            output_key=f"outputs/{uuid4()}.mp4",
            duration_s=37.8,
        )
        session.add(compilation)
        await session.commit()
        compilation_id = compilation.id

    resp = await client.get(f"/api/v1/compilations/{compilation_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["duration_s"] == pytest.approx(37.8)


async def test_get_compilation_duration_s_null_for_pending(
    test_env: dict[str, Any],
) -> None:
    """GET /compilations/{id} returns duration_s: null for a freshly created compilation."""
    client: AsyncClient = test_env["client"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    async with factory() as session:
        compilation = Compilation(status=CompilationStatus.pending)
        session.add(compilation)
        await session.commit()
        compilation_id = compilation.id

    resp = await client.get(f"/api/v1/compilations/{compilation_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["duration_s"] is None
