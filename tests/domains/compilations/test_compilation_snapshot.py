from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import _register_sqlite_pragmas
from app.domains.clips.models import Clip, ClipStatus
from app.domains.compilations.models import Compilation, CompilationClip


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _register_sqlite_pragmas(engine, busy_timeout_ms=5000)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as db_session:
        yield db_session

    await engine.dispose()


async def test_compilation_clip_snapshots_trim_independently(
    session: AsyncSession,
) -> None:
    clip = Clip(original_key="raw/a.mov", trim_in_s=1.0, trim_out_s=5.0)
    session.add(clip)
    await session.flush()

    compilation = Compilation()
    session.add(compilation)
    await session.flush()

    snapshot = CompilationClip(
        compilation_id=compilation.id,
        clip_id=clip.id,
        position=0,
        trim_in_s=clip.trim_in_s,
        trim_out_s=clip.trim_out_s,
    )
    session.add(snapshot)
    await session.commit()

    # Editing the source clip's trim must not retroactively change the snapshot.
    clip.trim_in_s = 2.0
    clip.trim_out_s = 4.0
    await session.commit()
    await session.refresh(snapshot)

    assert snapshot.trim_in_s == 1.0
    assert snapshot.trim_out_s == 5.0


async def test_clip_status_defaults_to_processing(session: AsyncSession) -> None:
    clip = Clip(original_key="raw/b.mov")
    session.add(clip)
    await session.flush()

    assert clip.status is ClipStatus.processing
