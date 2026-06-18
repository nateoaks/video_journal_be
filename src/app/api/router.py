from fastapi import APIRouter

from app.domains.clips.router import router as clips_router
from app.domains.items.router import router as items_router

api_router = APIRouter()
api_router.include_router(clips_router)
api_router.include_router(items_router)
