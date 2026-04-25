"""Add reading progress columns to knowledge_items

Revision ID: a3f7c8d91e02
Revises: ecb664f00845
Create Date: 2026-04-26 00:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f7c8d91e02'
down_revision: Union[str, Sequence[str], None] = '439923dea608'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add read_status, read_at, and last_opened_at columns to knowledge_items."""

    # Add read_status — server_default backfills all existing rows to "UNREAD"
    op.add_column(
        "knowledge_items",
        sa.Column(
            "read_status",
            sa.String(32),          # native_enum=False means it's just a VARCHAR
            nullable=False,
            server_default="UNREAD",
        ),
    )
    # Drop the server_default so future inserts use the Python-level default
    op.alter_column("knowledge_items", "read_status", server_default=None)

    # Add read_at — nullable, no default (only set when explicitly finished)
    op.add_column(
        "knowledge_items",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add last_opened_at — nullable, no default (only set on item detail views)
    op.add_column(
        "knowledge_items",
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Composite index for Library page filtering (Unread / Reading / Done tabs)
    op.create_index(
        "ix_knowledge_items_user_read_status",
        "knowledge_items",
        ["user_id", "read_status"],
    )


def downgrade() -> None:
    """Remove reading progress columns from knowledge_items."""
    op.drop_index("ix_knowledge_items_user_read_status", table_name="knowledge_items")
    op.drop_column("knowledge_items", "last_opened_at")
    op.drop_column("knowledge_items", "read_at")
    op.drop_column("knowledge_items", "read_status")
