"""Pydantic schemas for the soundtracks domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SoundtrackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    title: str
    duration_s: float | None
    uploaded_at: datetime
