from sqlalchemy import select

from app.common.repository import BaseRepository
from app.domains.items.models import Item


class ItemRepository(BaseRepository[Item]):
    model = Item

    async def get_by_name(self, name: str) -> Item | None:
        result = await self.session.execute(select(Item).where(Item.name == name))
        return result.scalar_one_or_none()
