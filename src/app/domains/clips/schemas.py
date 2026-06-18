import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.clips.models import ClipStatus


class ClipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_key: str
    normalized_key: str | None
    filmstrip_key: str | None
    duration_s: float | None
    width: int | None
    height: int | None
    codec_name: str | None
    recorded_at: datetime | None
    uploaded_at: datetime
    trim_in_s: float | None
    trim_out_s: float | None
    sort_index: float
    status: ClipStatus
    error_message: str | None


class ClipUpdate(BaseModel):
    trim_in_s: float | None = Field(default=None, ge=0)
    trim_out_s: float | None = Field(default=None, ge=0)
    sort_index: float | None = None
