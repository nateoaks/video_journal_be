"""create_soundtracks_table

Revision ID: 1c5f5dfd0769
Revises: 81950cc83b79
Create Date: 2026-06-18 09:55:58.446648

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1c5f5dfd0769'
down_revision: Union[str, Sequence[str], None] = '81950cc83b79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('soundtracks', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_soundtracks_uploaded_at'),
            ['uploaded_at'],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('soundtracks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_soundtracks_uploaded_at'))
