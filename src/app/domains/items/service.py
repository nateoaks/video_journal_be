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
