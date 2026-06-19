"""add_compilations_tables

Revision ID: 8e8cb7d9c562
Revises: 1c5f5dfd0769
Create Date: 2026-06-18 20:56:40.486502

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e8cb7d9c562"
down_revision: Union[str, Sequence[str], None] = "1c5f5dfd0769"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create compilations and compilation_clips tables."""
    op.create_table(
        "compilations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("soundtrack_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "complete", "failed", name="compilationstatus"
            ),
            nullable=False,
        ),
        sa.Column("output_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["soundtrack_id"], ["soundtracks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "compilation_clips",
        sa.Column("compilation_id", sa.Uuid(), nullable=False),
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("trim_in_s", sa.Float(), nullable=True),
        sa.Column("trim_out_s", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["clip_id"], ["clips.id"]),
        sa.ForeignKeyConstraint(["compilation_id"], ["compilations.id"]),
        sa.PrimaryKeyConstraint("compilation_id", "clip_id"),
    )


def downgrade() -> None:
    """Drop compilations and compilation_clips tables."""
    op.drop_table("compilation_clips")
    op.drop_table("compilations")
