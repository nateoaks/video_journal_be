"""Router for the storage domain."""

from fastapi import APIRouter

from app.domains.storage.dependencies import StorageUsageServiceDep
from app.domains.storage.schemas import StorageUsageRead

router = APIRouter(tags=["storage"])


@router.get("/usage", status_code=200)
async def get_storage_usage(service: StorageUsageServiceDep) -> StorageUsageRead:
    """Return on-disk storage usage broken down by media category."""
    return await service.compute_usage()
