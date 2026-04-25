"""Add color, emoji, is_default, default_content_type to collections

Revision ID: b8e1f2a3c9d0
Revises: a3f7c8d91e02
Create Date: 2026-04-26 01:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8e1f2a3c9d0'
down_revision: Union[str, Sequence[str], None] = 'a3f7c8d91e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add visual identity and auto-collection metadata to the collections table."""

    # color — hex string e.g. "#6366f1"
    op.add_column(
        "collections",
        sa.Column("color", sa.String(7), nullable=True),
    )

    # emoji — short unicode prefix e.g. "📰"
    op.add_column(
        "collections",
        sa.Column("emoji", sa.String(8), nullable=True),
    )

    # is_default — True for system-created collections
    op.add_column(
        "collections",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )

    # default_content_type — the content_type this default collection maps to.
    # NULL for custom collections.
    op.add_column(
        "collections",
        sa.Column("default_content_type", sa.String(), nullable=True),
    )

    # Index for efficient "list my collections" queries
    op.create_index("ix_collections_user_id", "collections", ["user_id"])


def downgrade() -> None:
    """Remove visual identity and auto-collection metadata from collections."""
    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_column("collections", "default_content_type")
    op.drop_column("collections", "is_default")
    op.drop_column("collections", "emoji")
    op.drop_column("collections", "color")
