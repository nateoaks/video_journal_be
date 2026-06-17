from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session

# Import every domain's models so Base.metadata is complete before create_all;
# cross-domain foreign keys (e.g. compilations -> soundtracks) need every table
# registered, not just the ones a given test imports directly.
from app.domains.clips import models as _clips_models  # noqa: F401
from app.domains.compilations import models as _compilations_models  # noqa: F401
from app.domains.items import models as _items_models  # noqa: F401
from app.domains.soundtracks import models as _soundtracks_models  # noqa: F401
from app.main import create_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    await engine.dispose()
