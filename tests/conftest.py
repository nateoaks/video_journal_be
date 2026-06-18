from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.domains.clips.router as clips_router_module
from app.db.base import Base
from app.db.session import get_session

# Import every domain's models so Base.metadata is complete before create_all;
# cross-domain foreign keys (e.g. compilations -> soundtracks) need every table
# registered, not just the ones a given test imports directly.
from app.domains.clips import models as _clips_models  # noqa: F401
from app.domains.clips.repository import ClipRepository
from app.domains.clips.service import ClipService
from app.domains.compilations import models as _compilations_models  # noqa: F401
from app.domains.items import models as _items_models  # noqa: F401
from app.domains.soundtracks import models as _soundtracks_models  # noqa: F401
from app.main import create_app
from app.storage import get_storage
from app.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    """Isolated LocalStorage instance backed by a temp directory."""
    return LocalStorage(tmp_path / "media")


@pytest.fixture
async def client(storage: LocalStorage) -> AsyncGenerator[AsyncClient]:
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

    async def override_get_background_clip_service() -> ClipService:
        """Background clip service wired to the test in-memory DB."""
        session = test_sessionmaker()
        return ClipService(ClipRepository(session), storage)

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_storage] = override_get_storage

    # Patch the background service factory used inside the router closure so
    # background tasks hit the same in-memory DB that the request session uses.
    original_bg_svc = clips_router_module.get_background_clip_service
    clips_router_module.get_background_clip_service = (  # type: ignore[assignment]
        override_get_background_clip_service
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    clips_router_module.get_background_clip_service = original_bg_svc  # type: ignore[assignment]
    await engine.dispose()
