"""Update collection is_default server default

Revision ID: 635223134eb3
Revises: b8e1f2a3c9d0
Create Date: 2026-04-26 01:40:58.659855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '635223134eb3'
down_revision: Union[str, Sequence[str], None] = 'b8e1f2a3c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Refine read_status to use the Enum validator (native_enum=False)
    op.alter_column('knowledge_items', 'read_status',
               existing_type=sa.VARCHAR(length=32),
               type_=sa.Enum('UNREAD', 'READING', 'DONE', name='read_status', native_enum=False),
               existing_nullable=False)

    # 2. Add server_default to is_default in collections
    op.alter_column('collections', 'is_default',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('false'),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('collections', 'is_default',
               existing_type=sa.BOOLEAN(),
               server_default=None,
               existing_nullable=False)

    op.alter_column('knowledge_items', 'read_status',
               existing_type=sa.Enum('UNREAD', 'READING', 'DONE', name='read_status', native_enum=False),
               type_=sa.VARCHAR(length=32),
               existing_nullable=False)
