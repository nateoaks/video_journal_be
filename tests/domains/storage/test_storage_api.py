"""Tests for GET /api/v1/storage/usage."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.domains.clips import models as _clips_models  # noqa: F401
from app.domains.compilations import models as _compilations_models  # noqa: F401
from app.domains.items import models as _items_models  # noqa: F401
from app.domains.soundtracks import models as _soundtracks_models  # noqa: F401
from app.main import create_app
from app.storage import get_storage
from app.storage.local import LocalStorage


@pytest.fixture
async def storage_client(tmp_path: Path) -> AsyncGenerator[tuple[AsyncClient, Path]]:
    """AsyncClient wired to an isolated storage backend at tmp_path."""
    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    storage = LocalStorage(media_root)

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_storage() -> LocalStorage:
        return storage

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_storage] = override_get_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client, media_root

    await engine.dispose()


async def test_empty_storage_returns_all_zeros(
    storage_client: tuple[AsyncClient, Path],
) -> None:
    """With no files present every category and the total should be 0."""
    client, _ = storage_client
    response = await client.get("/api/v1/storage/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["originals_bytes"] == 0
    assert data["normalized_bytes"] == 0
    assert data["filmstrips_bytes"] == 0
    assert data["soundtracks_bytes"] == 0
    assert data["outputs_bytes"] == 0
    assert data["total_bytes"] == 0


async def test_known_files_reflected_in_category_and_total(
    storage_client: tuple[AsyncClient, Path],
) -> None:
    """Files seeded in each prefix directory appear under the correct category."""
    client, media_root = storage_client

    def seed(subdir: str, size: int) -> None:
        d = media_root / subdir
        d.mkdir(parents=True, exist_ok=True)
        (d / "file.bin").write_bytes(b"x" * size)

    seed("clips/original", 100)
    seed("clips/normalized", 200)
    seed("clips/filmstrip", 300)
    seed("soundtracks", 400)
    seed("outputs", 500)

    response = await client.get("/api/v1/storage/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["originals_bytes"] == 100
    assert data["normalized_bytes"] == 200
    assert data["filmstrips_bytes"] == 300
    assert data["soundtracks_bytes"] == 400
    assert data["outputs_bytes"] == 500
    assert data["total_bytes"] == 1500


async def test_missing_category_directory_returns_zero(
    storage_client: tuple[AsyncClient, Path],
) -> None:
    """A category whose directory doesn't exist should report 0 bytes, not 500."""
    client, media_root = storage_client

    # Only seed one category; all others are missing directories.
    d = media_root / "clips" / "original"
    d.mkdir(parents=True, exist_ok=True)
    (d / "clip.mov").write_bytes(b"a" * 50)

    response = await client.get("/api/v1/storage/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["originals_bytes"] == 50
    assert data["normalized_bytes"] == 0
    assert data["filmstrips_bytes"] == 0
    assert data["soundtracks_bytes"] == 0
    assert data["outputs_bytes"] == 0
    assert data["total_bytes"] == 50


async def test_nested_subdirectory_files_included(
    storage_client: tuple[AsyncClient, Path],
) -> None:
    """Files in nested subdirectories are counted in the category total."""
    client, media_root = storage_client

    nested = media_root / "clips" / "original" / "2024" / "january"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "deep_file.mov").write_bytes(b"d" * 999)

    response = await client.get("/api/v1/storage/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["originals_bytes"] == 999
    assert data["total_bytes"] == 999
