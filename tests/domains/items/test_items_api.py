from httpx import AsyncClient


async def test_create_and_read_item(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "Widget"})
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "Widget"

    fetched = await client.get(f"/api/v1/items/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == item["id"]


async def test_list_items(client: AsyncClient) -> None:
    await client.post("/api/v1/items", json={"name": "A"})
    await client.post("/api/v1/items", json={"name": "B"})

    response = await client.get("/api/v1/items")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_update_item(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "Old"})
    item_id = created.json()["id"]

    updated = await client.patch(f"/api/v1/items/{item_id}", json={"name": "New"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "New"


async def test_delete_item(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "Temp"})
    item_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/items/{item_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/items/{item_id}")
    assert missing.status_code == 404


async def test_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_create_item_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": ""})
    assert response.status_code == 422
