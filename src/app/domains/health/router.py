from fastapi import APIRouter

from app.domains.health.schemas import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthStatus:
    return HealthStatus(status="ok")
