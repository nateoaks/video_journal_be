from uuid import UUID

from fastapi import APIRouter, status

from app.domains.items.dependencies import ItemServiceDep
from app.domains.items.schemas import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_item(data: ItemCreate, service: ItemServiceDep) -> ItemRead:
    item = await service.create(data)
    return ItemRead.model_validate(item)


@router.get("")
async def list_items(
    service: ItemServiceDep, limit: int = 50, offset: int = 0
) -> list[ItemRead]:
    items = await service.list(limit=limit, offset=offset)
    return [ItemRead.model_validate(item) for item in items]


@router.get("/{item_id}")
async def get_item(item_id: UUID, service: ItemServiceDep) -> ItemRead:
    item = await service.get(item_id)
    return ItemRead.model_validate(item)


@router.patch("/{item_id}")
async def update_item(
    item_id: UUID, data: ItemUpdate, service: ItemServiceDep
) -> ItemRead:
    item = await service.update(item_id, data)
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: UUID, service: ItemServiceDep) -> None:
    await service.delete(item_id)
