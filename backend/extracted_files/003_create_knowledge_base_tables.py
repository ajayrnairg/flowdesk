"""
alembic/versions/003_create_knowledge_base_tables.py
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_create_knowledge_base"
down_revision = "002_create_notifications"  # ← point to your last migration
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── knowledge_items ───────────────────────────────────────────────────
    op.create_table(
        "knowledge_items",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("url",                    sa.Text,         nullable=True),
        sa.Column("title",                  sa.String(500),  nullable=True),
        sa.Column("summary",                sa.Text,         nullable=True),
        sa.Column("content_type",           sa.String(32),   nullable=False),
        sa.Column("raw_text",               sa.Text,         nullable=True),
        sa.Column("cover_image_url",        sa.Text,         nullable=True),
        sa.Column("estimated_read_minutes", sa.Integer,      nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String),
            nullable=True,
        ),
        sa.Column(
            "is_processed", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )

    # Indexes — see rationale in models/knowledge.py
    op.create_index("ix_ki_user_created",      "knowledge_items", ["user_id", "created_at"])
    op.create_index("ix_ki_user_content_type", "knowledge_items", ["user_id", "content_type"])
    op.create_index("ix_ki_user_status",       "knowledge_items", ["user_id", "status"])

    # updated_at trigger (reuses the function from the tasks migration if it exists)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER knowledge_items_updated_at
        BEFORE UPDATE ON knowledge_items
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ── collections ───────────────────────────────────────────────────────
    op.create_table(
        "collections",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name",        sa.String(255), nullable=False),
        sa.Column("description", sa.Text,        nullable=True),
        sa.Column("color",       sa.String(7),   nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    # ── collection_items ──────────────────────────────────────────────────
    op.create_table(
        "collection_items",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "collection_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "knowledge_item_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "added_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("collection_id", "knowledge_item_id", name="uq_collection_item"),
    )
    op.create_index("ix_ci_collection_added",    "collection_items", ["collection_id", "added_at"])
    op.create_index("ix_ci_knowledge_item_id",   "collection_items", ["knowledge_item_id"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_updated_at ON knowledge_items;")
    op.drop_index("ix_ci_knowledge_item_id",   table_name="collection_items")
    op.drop_index("ix_ci_collection_added",    table_name="collection_items")
    op.drop_table("collection_items")
    op.drop_index("ix_collections_user_id",    table_name="collections")
    op.drop_table("collections")
    op.drop_index("ix_ki_user_status",         table_name="knowledge_items")
    op.drop_index("ix_ki_user_content_type",   table_name="knowledge_items")
    op.drop_index("ix_ki_user_created",        table_name="knowledge_items")
    op.drop_table("knowledge_items")
