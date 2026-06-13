# Data Models

Every domain separates three concerns: **ORM models** (the database), **schemas** (the
API contract), and the **repository** (data access). They never collapse into one class.

## ORM models (`models.py`)

SQLAlchemy 2.0 declarative models using `Mapped[...]` + `mapped_column`. All models
inherit the shared `Base` from `app.db.base`.

```python
# src/app/domains/items/models.py
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
```

Rules:
- **UUID primary keys**, never auto-increment integers. `default=uuid.uuid4`.
- `__tablename__` is **snake_case and plural** (`items`, `order_lines`).
- Use `Mapped[T]` for every column; nullability comes from `Mapped[T | None]`, not a
  `nullable=` kwarg.
- Timestamps via `server_default=func.now()`; `onupdate=func.now()` for `updated_at`.
- Relationships use `Mapped[list["Other"]]` / `Mapped["Other"]` with `relationship()` and
  an explicit `ForeignKey`.

## Schemas (`schemas.py`)

Pydantic v2 models — the **only** types that cross the HTTP boundary. Split by purpose:

```python
# src/app/domains/items/schemas.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

Rules:
- `*Create` — fields required to create; omit server-generated fields (`id`, timestamps).
- `*Update` — every field optional (partial update / `PATCH`).
- `*Read` — the response shape; `model_config = ConfigDict(from_attributes=True)` so it can
  be built from an ORM instance via `ItemRead.model_validate(entity)`.
- Validate input at the edge with `Field(...)` constraints; don't re-validate in services.

## Repository (`repository.py`)

The only place that runs queries. Extends the generic `BaseRepository` from
`app.common.repository`, which provides `get`, `list`, `add`, and `delete`.

The base lives in `app.common.repository` and uses PEP 695 generics
(`class BaseRepository[ModelT: Base]`). A concrete repository binds the type and sets
`model`:

```python
# src/app/domains/items/repository.py
from sqlalchemy import select

from app.common.repository import BaseRepository
from app.domains.items.models import Item


class ItemRepository(BaseRepository[Item]):
    model = Item

    async def get_by_name(self, name: str) -> Item | None:
        result = await self.session.execute(select(Item).where(Item.name == name))
        return result.scalar_one_or_none()
```

Rules:
- Set the `model` class attribute so the base helpers know which table to target.
- Add typed, intention-revealing query methods (`get_by_name`, `list_active`) instead of
  exposing raw `select()` calls to the service.
- Repositories `flush()` (so generated IDs/defaults are available) but **never `commit()`**.
  The commit happens once per request in the `get_session` dependency.

## Service (`service.py`)

Business logic. Depends on the repository, raises domain errors, returns ORM instances to
the router (which converts them to schemas).

```python
# src/app/domains/items/service.py
from collections.abc import Sequence
from uuid import UUID

from app.common.exceptions import NotFoundError
from app.domains.items.models import Item
from app.domains.items.repository import ItemRepository
from app.domains.items.schemas import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    async def create(self, data: ItemCreate) -> Item:
        item = Item(name=data.name, description=data.description)
        return await self.repository.add(item)

    async def get(self, item_id: UUID) -> Item:
        item = await self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        return item

    async def list(self, limit: int = 50, offset: int = 0) -> Sequence[Item]:
        return await self.repository.list(limit=limit, offset=offset)

    async def update(self, item_id: UUID, data: ItemUpdate) -> Item:
        item = await self.get(item_id)
        if data.name is not None:
            item.name = data.name
        if data.description is not None:
            item.description = data.description
        return await self.repository.add(item)

    async def delete(self, item_id: UUID) -> None:
        item = await self.get(item_id)
        await self.repository.delete(item)
```

See `docs/code-design.md` for how to decompose larger services and `docs/code-style.md`
for error-handling rules.
