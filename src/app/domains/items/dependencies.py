from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.domains.items.repository import ItemRepository
from app.domains.items.service import ItemService


def get_item_service(session: SessionDep) -> ItemService:
    return ItemService(ItemRepository(session))


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
