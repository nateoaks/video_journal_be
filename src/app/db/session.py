from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _register_sqlite_pragmas(engine: AsyncEngine, busy_timeout_ms: int) -> None:
    """Apply WAL mode, a busy timeout, and FK enforcement on every connection.

    WAL is persisted on the database file, but the busy timeout and
    ``foreign_keys`` pragma are per-connection and must be set each time.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(
        dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite"):
            _engine = create_async_engine(
                settings.database_url,
                connect_args={"check_same_thread": False},
            )
            _register_sqlite_pragmas(_engine, settings.sqlite_busy_timeout_ms)
        else:
            _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Request-scoped unit of work: commit on success, roll back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
