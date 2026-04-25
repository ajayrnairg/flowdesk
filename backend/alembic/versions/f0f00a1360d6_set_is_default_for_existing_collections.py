"""Set is_default for existing collections

Revision ID: f0f00a1360d6
Revises: 635223134eb3
Create Date: 2026-04-26 01:43:05.987678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0f00a1360d6'
down_revision: Union[str, Sequence[str], None] = '635223134eb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Mark existing system collections as default based on their emoji prefixes."""
    # Note: We use LIKE '📰%' etc. to match collections that start with these emojis
    op.execute(
        "UPDATE collections SET is_default = true "
        "WHERE name LIKE '📰%' OR name LIKE '🎥%' OR name LIKE '💻%' "
        "OR name LIKE '💬%' OR name LIKE '📄%'"
    )


def downgrade() -> None:
    """Revert is_default to false for these collections."""
    op.execute(
        "UPDATE collections SET is_default = false "
        "WHERE name LIKE '📰%' OR name LIKE '🎥%' OR name LIKE '💻%' "
        "OR name LIKE '💬%' OR name LIKE '📄%'"
    )
