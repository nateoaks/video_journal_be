import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompilationStatus(enum.StrEnum):
    """Lifecycle of a compilation render job."""

    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


class CompilationClip(Base):
    """A frozen snapshot of one clip's place in a compilation's timeline.

    Position and trim points are copied here at compile time so that later edits
    to the source clip never retroactively alter a past compilation's record.
    """

    __tablename__ = "compilation_clips"

    compilation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compilations.id"), primary_key=True
    )
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id"), primary_key=True)
    position: Mapped[int]
    trim_in_s: Mapped[float | None] = mapped_column(default=None)
    trim_out_s: Mapped[float | None] = mapped_column(default=None)


class Compilation(Base):
    __tablename__ = "compilations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    soundtrack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("soundtracks.id"), default=None
    )
    status: Mapped[CompilationStatus] = mapped_column(
        Enum(CompilationStatus, native_enum=False),
        default=CompilationStatus.pending,
    )
    output_key: Mapped[str | None] = mapped_column(default=None)
    duration_s: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    error: Mapped[str | None] = mapped_column(default=None)

    # lazy="noload" prevents SQLAlchemy from issuing implicit SELECT queries in
    # async contexts.  Callers that need clips must use selectinload (repository)
    # or populate the list in-memory (service.create).  This relies on
    # expire_on_commit=False on the sessionmaker so attribute access after commit
    # doesn't trigger a lazy-load attempt.
    clips: Mapped[list[CompilationClip]] = relationship(
        "CompilationClip", lazy="noload"
    )
