"""Integration tests for mix_clip_audio / clip_audio_volume fields."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
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
from app.storage import get_storage
from app.storage.local import LocalStorage

_FAKE_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"


@pytest.fixture
async def test_env(tmp_path: Path) -> AsyncGenerator[dict[str, Any]]:
    """Isolated DB + storage with all overrides wired."""
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
        }

    compilations_router_module.get_background_compilation_service = original_bg_svc  # type: ignore[assignment]
    await engine.dispose()


async def _seed_ready_clip(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
    sort_index: float = 1000.0,
) -> None:
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


async def _seed_soundtrack(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
) -> str:
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
    return str(soundtrack.id)


async def _stub_render(
    self: CompilationService, *args: object, **kwargs: object
) -> None:
    return


async def test_defaults_returned_when_fields_omitted(
    test_env: dict[str, Any],
) -> None:
    """POST without mix_clip_audio fields → GET returns defaults (false, 0.4)."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    await _seed_ready_clip(storage, factory)
    soundtrack_id = await _seed_soundtrack(storage, factory)

    original_run = CompilationService.run_compilation
    CompilationService.run_compilation = _stub_render  # type: ignore[method-assign]
    try:
        resp = await client.post(
            "/api/v1/compilations",
            json={"soundtrack_id": soundtrack_id},
        )
    finally:
        CompilationService.run_compilation = original_run  # type: ignore[method-assign]

    assert resp.status_code == 202
    body = resp.json()
    assert body["mix_clip_audio"] is False
    assert body["clip_audio_volume"] == pytest.approx(0.4)

    compilation_id = body["id"]
    get_resp = await client.get(f"/api/v1/compilations/{compilation_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["mix_clip_audio"] is False
    assert get_body["clip_audio_volume"] == pytest.approx(0.4)


async def test_mix_clip_audio_fields_persisted(
    test_env: dict[str, Any],
) -> None:
    """POST with mix_clip_audio=true, clip_audio_volume=0.7 → GET returns those values."""
    client: AsyncClient = test_env["client"]
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    await _seed_ready_clip(storage, factory)
    soundtrack_id = await _seed_soundtrack(storage, factory)

    original_run = CompilationService.run_compilation
    CompilationService.run_compilation = _stub_render  # type: ignore[method-assign]
    try:
        resp = await client.post(
            "/api/v1/compilations",
            json={
                "soundtrack_id": soundtrack_id,
                "mix_clip_audio": True,
                "clip_audio_volume": 0.7,
            },
        )
    finally:
        CompilationService.run_compilation = original_run  # type: ignore[method-assign]

    assert resp.status_code == 202
    body = resp.json()
    assert body["mix_clip_audio"] is True
    assert body["clip_audio_volume"] == pytest.approx(0.7)

    compilation_id = body["id"]
    get_resp = await client.get(f"/api/v1/compilations/{compilation_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["mix_clip_audio"] is True
    assert get_body["clip_audio_volume"] == pytest.approx(0.7)


async def test_clip_audio_volume_above_1_rejected(
    test_env: dict[str, Any],
) -> None:
    """clip_audio_volume > 1.0 is rejected with 422."""
    client: AsyncClient = test_env["client"]
    resp = await client.post(
        "/api/v1/compilations",
        json={
            "soundtrack_id": str(uuid4()),
            "clip_audio_volume": 1.5,
        },
    )
    assert resp.status_code == 422


async def test_clip_audio_volume_below_0_rejected(
    test_env: dict[str, Any],
) -> None:
    """clip_audio_volume < 0.0 is rejected with 422."""
    client: AsyncClient = test_env["client"]
    resp = await client.post(
        "/api/v1/compilations",
        json={
            "soundtrack_id": str(uuid4()),
            "clip_audio_volume": -0.1,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Service-level unit test: run_compilation forwards fields to compile_video
# ---------------------------------------------------------------------------


async def _seed_compilation_for_unit_test(
    storage: LocalStorage,
    factory: async_sessionmaker[AsyncSession],
    mix_clip_audio: bool,
    clip_audio_volume: float,
) -> UUID:
    """Seed a pending compilation row with one clip snapshot and a soundtrack."""
    clip_key = f"clips/normalized/{uuid4()}.mp4"
    clip_path = Path(storage.path_or_url(clip_key))
    await anyio.to_thread.run_sync(
        lambda: (
            clip_path.parent.mkdir(parents=True, exist_ok=True),
            clip_path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"),
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
            mix_clip_audio=mix_clip_audio,
            clip_audio_volume=clip_audio_volume,
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


async def test_run_compilation_forwards_mix_fields_to_compile_video(
    test_env: dict[str, Any],
) -> None:
    """run_compilation passes mix_clip_audio and clip_audio_volume to compile_video."""
    storage: LocalStorage = test_env["storage"]
    factory: async_sessionmaker[AsyncSession] = test_env["factory"]

    compilation_id = await _seed_compilation_for_unit_test(
        storage, factory, mix_clip_audio=True, clip_audio_volume=0.7
    )

    mock_compile = AsyncMock(return_value=None)

    original_probe = svc_module.probe

    async def _fake_probe(path: object) -> object:
        from app.media.ffprobe import ProbeResult

        return ProbeResult(
            duration_s=5.0, width=1920, height=1080, codec_name="h264", recorded_at=None
        )

    svc_module.probe = _fake_probe  # type: ignore[assignment]

    try:
        with patch("app.domains.compilations.service.compile_video", mock_compile):
            async with factory() as session:
                svc = CompilationService(CompilationRepository(session), storage)
                await svc.run_compilation(compilation_id)
    finally:
        svc_module.probe = original_probe  # type: ignore[assignment]

    mock_compile.assert_awaited_once()
    _call_kwargs = mock_compile.call_args.kwargs
    assert _call_kwargs["mix_clip_audio"] is True
    assert _call_kwargs["clip_audio_volume"] == pytest.approx(0.7)
