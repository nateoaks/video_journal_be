# Testing

Tests use **pytest** with **pytest-asyncio** (auto mode) and **httpx**'s `AsyncClient`
driving the ASGI app in-process. The suite runs against an in-memory SQLite database, so it
needs no Postgres and no network.

```bash
uv run pytest            # run the suite
uv run pytest -q         # quiet
uv run pytest --cov      # with coverage
```

## Layout

Tests live in `tests/`, mirroring `src/app/`:

```
tests/
├── conftest.py                     ← shared fixtures (the `client` fixture)
├── test_health.py
└── domains/
    └── items/
        └── test_items_api.py
```

## The `client` fixture

`conftest.py` provides an `AsyncClient` wired to a fresh, isolated database per test. It
creates the schema from `Base.metadata`, overrides the app's `get_session` dependency to use
a SQLite session, and tears everything down afterward:

```python
# tests/conftest.py
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    await engine.dispose()
```

`StaticPool` + `check_same_thread=False` keep the in-memory database alive across the
requests within a single test.

## Writing tests

Because pytest-asyncio runs in **auto mode**, async test functions need no decorator:

```python
# tests/domains/items/test_items_api.py
from httpx import AsyncClient


async def test_create_and_read_item(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "Widget"})
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "Widget"

    fetched = await client.get(f"/api/v1/items/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == item["id"]


async def test_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/items/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
```

## Guidelines

- **Test behavior through the API** for endpoints — assert on status codes and response
  bodies, not on internal calls.
- **Unit-test services in isolation** when the logic is non-trivial: construct the service
  with a mocked or fake repository and assert on its behavior. DI makes this straightforward
  (see `docs/code-design.md`).
- Each test is independent — the `client` fixture gives every test a clean database. Never
  rely on ordering or leftover state.
- `assert` is allowed here (ruff's `S101` is disabled for `tests/`).
- Test the error paths, not just the happy path: validation failures, missing resources,
  conflicts.
