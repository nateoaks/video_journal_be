"""add compilations mix clip audio

Revision ID: 730bc015c129
Revises: 46946a54cc08
Create Date: 2026-06-24 18:58:54.975115

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '730bc015c129'
down_revision: Union[str, Sequence[str], None] = '46946a54cc08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('compilations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'mix_clip_audio',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                'clip_audio_volume',
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.4"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('compilations', schema=None) as batch_op:
        batch_op.drop_column('clip_audio_volume')
        batch_op.drop_column('mix_clip_audio')
