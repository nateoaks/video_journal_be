"""FastAPI dependency providers for the storage domain."""

from typing import Annotated

from fastapi import Depends

from app.domains.storage.service import StorageUsageService
from app.storage.dependencies import StorageDep


def get_storage_usage_service(storage: StorageDep) -> StorageUsageService:
    return StorageUsageService(storage)


StorageUsageServiceDep = Annotated[
    StorageUsageService, Depends(get_storage_usage_service)
]
