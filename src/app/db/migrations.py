from pathlib import Path

from alembic import command
from alembic.config import Config

# src/app/db/migrations.py -> repo root is four levels up.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


def run_migrations() -> None:
    """Upgrade the database to the latest revision.

    This is synchronous (Alembic drives its own event loop in ``env.py``), so
    callers on an async path must offload it to a worker thread.
    """
    config = Config(str(_ALEMBIC_INI))
    command.upgrade(config, "head")
