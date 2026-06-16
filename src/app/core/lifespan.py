from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI

from app.core.logging import get_logger
from app.db.migrations import run_migrations
from app.db.session import get_engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger.info("application.startup")
    await anyio.to_thread.run_sync(run_migrations)
    logger.info("db.migrations.applied")
    yield
    await get_engine().dispose()
    logger.info("application.shutdown")
