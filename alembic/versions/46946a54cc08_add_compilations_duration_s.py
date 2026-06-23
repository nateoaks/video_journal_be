"""add compilations duration_s

Revision ID: 46946a54cc08
Revises: 8e8cb7d9c562
Create Date: 2026-06-23 10:23:28.611923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46946a54cc08'
down_revision: Union[str, Sequence[str], None] = '8e8cb7d9c562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('compilations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('duration_s', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('compilations', schema=None) as batch_op:
        batch_op.drop_column('duration_s')
