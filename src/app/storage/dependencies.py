from typing import Annotated

from fastapi import Depends

from app.storage import get_storage
from app.storage.base import StorageBackend

StorageDep = Annotated[StorageBackend, Depends(get_storage)]
