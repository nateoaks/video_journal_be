# Code Design

## Function decomposition

A service method should read like an outline: it names the steps and delegates each to a
focused helper. Don't write long top-to-bottom procedures.

```python
async def create_order(self, data: OrderCreate) -> Order:
    await self._validate_stock(data)
    pricing = self._calculate_pricing(data)
    order = await self.repository.add(Order(**data.model_dump(), **pricing.as_dict()))
    await self._notify_warehouse(order)
    return order

async def _validate_stock(self, data: OrderCreate) -> None:
    # raises ConflictError if anything is out of stock
    ...

def _calculate_pricing(self, data: OrderCreate) -> Pricing:
    # pure function — trivial to unit test in isolation
    ...
```

Rules:
- Extract non-trivial validation (multi-step guards, cross-entity checks) into a private
  method that runs **before** the main logic and raises on failure.
- Each helper does one thing and is named for what it does.
- Prefer returning a typed result object from a helper over mutating shared state.

## Pure helpers belong outside classes

Stateless logic with no `self` dependency (date math, formatting, pagination math) should be
a module-level function, not a method — it's easier to test and reuse.

- **Generic, reusable** helpers → `app/common/`.
- **Domain-specific** helpers used by one feature → a `<domain>/utils.py` module beside the
  service.

Never bury a pure function inside a class just for convenience.

## Dependency injection

Services receive their collaborators through `__init__`; FastAPI assembles the graph via the
providers in each domain's `dependencies.py`:

```python
# src/app/domains/items/dependencies.py
from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.domains.items.repository import ItemRepository
from app.domains.items.service import ItemService


def get_item_service(session: SessionDep) -> ItemService:
    return ItemService(ItemRepository(session))


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
```

This keeps services free of global state: they never reach for the session, settings, or a
singleton directly — everything they need is passed in. That is what makes them unit-testable
with a mocked repository, and what lets tests override the database session wholesale.

## Error handling

- Raise domain errors from `app.common.exceptions` (`NotFoundError`, `ConflictError`, …) in
  services. A single exception handler maps them to the right HTTP status — endpoints don't
  build error responses by hand.
- Catch **specific** exceptions, never bare `except:` or a blanket `except Exception:` that
  swallows everything.
- Surface actionable messages. Never silently discard an error.
- Let unexpected exceptions propagate to the global handler rather than catching and hiding
  them at every layer.

## Async discipline

This is an async codebase end to end.

- Use `async def` for anything that touches the database or makes network calls, and `await`
  every coroutine.
- **Never** call a blocking function (sync DB driver, `requests`, `time.sleep`, heavy CPU
  work) inside an async path — it stalls the event loop. Offload genuinely blocking work with
  `anyio.to_thread.run_sync(...)`.
- Database access goes through the injected `AsyncSession` only.
