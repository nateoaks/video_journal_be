import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClipStatus(enum.StrEnum):
    """Lifecycle of an uploaded clip as it moves through processing."""

    processing = "processing"
    ready = "ready"
    failed = "failed"


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Storage key for the raw upload; the only key known at creation time.
    original_key: Mapped[str]
    # Keys for the transcoded clip and its filmstrip thumbnail strip, filled in
    # once processing completes.
    normalized_key: Mapped[str | None] = mapped_column(default=None)
    filmstrip_key: Mapped[str | None] = mapped_column(default=None)
    duration_s: Mapped[float | None] = mapped_column(default=None)
    width: Mapped[int | None] = mapped_column(default=None)
    height: Mapped[int | None] = mapped_column(default=None)
    codec_name: Mapped[str | None] = mapped_column(default=None)
    recorded_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # User-chosen trim window applied when this clip is included in a compilation.
    trim_in_s: Mapped[float | None] = mapped_column(default=None)
    trim_out_s: Mapped[float | None] = mapped_column(default=None)
    # Fractional index so clips can be reordered without renumbering siblings.
    sort_index: Mapped[float] = mapped_column(default=0.0, index=True)
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus, native_enum=False),
        default=ClipStatus.processing,
    )
