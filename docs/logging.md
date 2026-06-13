# Logging

Logging uses **structlog**. It is configured once in `src/app/core/logging.py` and
produces human-friendly console output locally and JSON in every other environment.

## Getting a logger

```python
from app.core.logging import get_logger

logger = get_logger(__name__)


async def do_work(item_id: str) -> None:
    logger.info("item.processing.started", item_id=item_id)
    ...
    logger.info("item.processing.finished", item_id=item_id, duration_ms=12)
```

## Conventions

- **Never use `print()`** for diagnostics. Use the logger.
- Event names are short, lowercase, dot-namespaced verbs in the past/imperative:
  `item.created`, `payment.failed`, `db.query.slow`. The event string is a stable key —
  put the variable data in **keyword arguments**, not in an f-string.

  ```python
  # right — structured, queryable
  logger.info("user.login", user_id=user.id, method="password")

  # wrong — unstructured, unsearchable
  logger.info(f"User {user.id} logged in via password")
  ```

- Choose levels deliberately: `debug` for development detail, `info` for normal lifecycle
  events, `warning` for recoverable problems, `error` for failures that need attention.
  Log level threshold comes from `LOG_LEVEL` in the environment.
- Log exceptions with `logger.exception("...")` inside an `except` block to capture the
  traceback; do not log and re-raise the same error at multiple layers.

## Request correlation

`app/core/middleware.py` installs an ASGI middleware that binds a unique `request_id` into
structlog's context vars for every HTTP request and echoes it back as the `X-Request-ID`
response header. Every log line emitted while handling that request automatically carries
the `request_id` — you don't pass it around manually.

To attach more context for the duration of a request (e.g. the authenticated user), bind it
once and it flows to all subsequent log lines:

```python
import structlog

structlog.contextvars.bind_contextvars(user_id=user.id)
```
