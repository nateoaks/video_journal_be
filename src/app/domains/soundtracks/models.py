import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Soundtrack(Base):
    __tablename__ = "soundtracks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str]
    title: Mapped[str]
    duration_s: Mapped[float | None] = mapped_column(default=None)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
