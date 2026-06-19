"""Pydantic schemas for the compilations domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.compilations.models import CompilationStatus


class CompilationCreate(BaseModel):
    """Request body for creating a new compilation."""

    soundtrack_id: uuid.UUID


class CompilationClipRead(BaseModel):
    """A frozen snapshot of one clip's place in a compilation timeline."""

    model_config = ConfigDict(from_attributes=True)

    clip_id: uuid.UUID
    position: int
    trim_in_s: float | None
    trim_out_s: float | None


class CompilationRead(BaseModel):
    """Response schema for a compilation record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CompilationStatus
    soundtrack_id: uuid.UUID | None
    output_key: str | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    clips: list[CompilationClipRead]
