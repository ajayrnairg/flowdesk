"""create knowledge chunks table

Revision ID: 439923dea608
Revises: ecb664f00845
Create Date: 2026-04-25 03:30:58.762332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '439923dea608'
down_revision: Union[str, Sequence[str], None] = 'ecb664f00845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure pgvector extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('knowledge_item_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Add B-tree indexes on user_id and knowledge_item_id columns
    op.create_index('ix_kc_user_id', 'knowledge_chunks', ['user_id'], unique=False)
    op.create_index('ix_kc_knowledge_item_id', 'knowledge_chunks', ['knowledge_item_id'], unique=False)

    # 4. Add the vector similarity index using raw SQL
    op.execute("""
      CREATE INDEX knowledge_chunks_embedding_hnsw_idx
      ON knowledge_chunks
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 5. Drop the HNSW index before dropping the table
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx;")
    
    op.drop_index('ix_kc_knowledge_item_id', table_name='knowledge_chunks')
    op.drop_index('ix_kc_user_id', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
