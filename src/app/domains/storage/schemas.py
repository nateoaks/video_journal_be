"""Pydantic schemas for the storage domain."""

from pydantic import BaseModel, ConfigDict


class StorageUsageRead(BaseModel):
    """Disk usage broken down by media category and total."""

    model_config = ConfigDict(from_attributes=True)

    originals_bytes: int
    normalized_bytes: int
    filmstrips_bytes: int
    soundtracks_bytes: int
    outputs_bytes: int
    total_bytes: int
