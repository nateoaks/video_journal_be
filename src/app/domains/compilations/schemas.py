"""Pydantic schemas for the compilations domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.compilations.models import CompilationStatus


class CompilationCreate(BaseModel):
    """Request body for creating a new compilation.

    mix_clip_audio: If True, concatenated clip audio streams are mixed under the
    soundtrack. If False (default), only the soundtrack is used for audio output.

    clip_audio_volume: Weight for clip audio in the mix (0.0-1.0). Only used when
    mix_clip_audio is True. Larger values make clip audio louder relative to the
    soundtrack. Defaults to 0.4.
    """

    soundtrack_id: uuid.UUID
    mix_clip_audio: bool = False
    clip_audio_volume: float = Field(default=0.4, ge=0.0, le=1.0)


class CompilationClipRead(BaseModel):
    """A frozen snapshot of one clip's place in a compilation timeline."""

    model_config = ConfigDict(from_attributes=True)

    clip_id: uuid.UUID
    position: int
    trim_in_s: float | None
    trim_out_s: float | None


class CompilationRead(BaseModel):
    """Response schema for a compilation record.

    Fields mix_clip_audio and clip_audio_volume reflect the audio mixing settings
    that were applied during rendering. They are always present, even if the
    compilation is still pending or has failed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CompilationStatus
    soundtrack_id: uuid.UUID | None
    output_key: str | None
    duration_s: float | None
    mix_clip_audio: bool
    clip_audio_volume: float
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    clips: list[CompilationClipRead]
