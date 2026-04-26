"""add clerk_user_id

Revision ID: 433aa93d1a37
Revises: f0f00a1360d6
Create Date: 2026-04-26 15:33:56.451230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '433aa93d1a37'
down_revision: Union[str, Sequence[str], None] = 'f0f00a1360d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add clerk_user_id — nullable so existing rows are unaffected.
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(255), nullable=True),
    )

    # Unique constraint — one Clerk identity maps to exactly one FlowDesk user.
    op.create_unique_constraint(
        "uq_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
    )

    # Btree index for the WHERE clerk_user_id = ? lookup in get_current_user.
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_constraint("uq_users_clerk_user_id", "users", type_="unique")
    op.drop_column("users", "clerk_user_id")
