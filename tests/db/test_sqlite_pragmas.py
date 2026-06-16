from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.session import _register_sqlite_pragmas


async def test_wal_and_pragmas_are_applied(tmp_path: Path) -> None:
    db_path = tmp_path / "journal.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    _register_sqlite_pragmas(engine, busy_timeout_ms=5000)

    async with engine.connect() as conn:
        journal_mode = await conn.scalar(text("PRAGMA journal_mode"))
        busy_timeout = await conn.scalar(text("PRAGMA busy_timeout"))
        foreign_keys = await conn.scalar(text("PRAGMA foreign_keys"))

    await engine.dispose()

    assert journal_mode == "wal"
    assert busy_timeout == 5000
    assert foreign_keys == 1
