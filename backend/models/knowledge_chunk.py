"""
models/knowledge_chunk.py — pgvector chunk model for FlowDesk RAG pipeline.

─────────────────────────────────────────────────────────────────────────────
VECTOR INDEX DECISION: HNSW over IVFFlat for this use case
─────────────────────────────────────────────────────────────────────────────

IVFFlat (Inverted File with Flat storage)
  • Divides vectors into `lists` Voronoi cells at index build time.
  • Search scans `probes` cells (default 1, tune upward for better recall).
  • Build time is fast; memory is low.
  • Critical flaw: recall degrades as the dataset grows past ~10x the list
    count. For personal use (hundreds to low-thousands of chunks, say
    500–10k vectors) you'd need lists ≈ sqrt(n) ≈ 22–100. With that few
    lists the index barely helps — pgvector may fall back to sequential scan.
  • Another flaw: IVFFlat requires a training phase on existing data.
    An empty or near-empty table produces a broken index that must be
    REINDEX-ed after data grows. This is painful for a product where users
    add items incrementally.

HNSW (Hierarchical Navigable Small World)
  • Graph-based index: each vector is connected to its nearest neighbours
    at multiple layers of a skip-list-like hierarchy.
  • No training phase — vectors are inserted incrementally and the graph
    stays valid. Ideal for a product with continuous ingestion.
  • Better recall than IVFFlat at equivalent query speed for small-to-medium
    datasets (under ~1M vectors).
  • Higher memory overhead per vector (~8–16 bytes * m links), but at
    10k chunks with 768-dim embeddings this is negligible (<50 MB).
  • ef_construction: controls build quality (default 64, range 8–200).
    Higher = better index, slower build. 64 is fine for this use case.
  • m: number of connections per layer (default 16, range 2–100).
    Higher = better recall, more memory. 16 is correct for this size.

VERDICT: HNSW with m=16, ef_construction=64, cosine distance (vector_cosine_ops).
  text-embedding-004 outputs unit-normalised vectors, so cosine similarity
  and dot product are equivalent. We use cosine because pgvector's
  vector_cosine_ops HNSW index is more widely tested and documented.

NOTE ON INDEX CREATION:
  The HNSW vector index (ix_kc_embedding_hnsw) CANNOT be created via
  SQLAlchemy's Index() — SQLAlchemy does not support the postgresql_with
  storage parameters required by pgvector (m, ef_construction). It must be
  added as raw SQL in the Alembic migration:

      op.execute(\"\"\"
          CREATE INDEX ix_kc_embedding_hnsw
          ON knowledge_chunks
          USING hnsw (embedding vector_cosine_ops)
          WITH (m = 16, ef_construction = 64);
      \"\"\")

  Only standard B-tree indexes are declared here in __table_args__.
─────────────────────────────────────────────────────────────────────────────
"""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

EMBEDDING_DIM = 768  # text-embedding-004 output dimension


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Denormalised from knowledge_items.user_id.
    # Without this, every ANN search query would require a JOIN to
    # knowledge_items just to scope results to the requesting user.
    # JOINs and vector index scans interact badly in Postgres — the planner
    # often degrades to a sequential scan when a JOIN is involved.
    # Storing user_id directly lets us filter BEFORE the ANN scan:
    #   WHERE user_id = ? ORDER BY embedding <=> query_vec LIMIT k
    # This is the standard pgvector pattern for multi-tenant apps.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 0-based position within the parent item. Used to reconstruct reading
    # order when returning multiple chunks from the same item, and to
    # re-chunk deterministically if the embedding model changes.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    # pgvector column. DIM must match the embedding model exactly.
    # text-embedding-004: 768 dimensions (default; configurable down to 256
    # with output_dimensionality param, but 768 is the canonical choice).
    embedding: Mapped[list] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    # lazy="raise" prevents accidental N+1 loads; callers must use
    # selectinload() / joinedload() explicitly in async queries.
    knowledge_item = relationship(
        "KnowledgeItem",
        back_populates="chunks",
        lazy="raise",
    )

    __table_args__ = (
        # ── Scalar B-tree indexes ────────────────────────────────────────────
        #
        # (a) User-scoped chunk lookup — primary pre-filter before ANN.
        #     Used by: search pipeline (WHERE user_id = ?)
        #     This is a plain btree; the vector index handles ordering.
        Index("ix_kc_user_id", "user_id"),

        # (b) Item-scoped lookup — used for deletion and re-embedding.
        #     When a KnowledgeItem is deleted, Postgres cascades the FK,
        #     but we also need to efficiently find chunks to delete manually
        #     on re-ingestion (re-chunk replaces existing chunks).
        Index("ix_kc_knowledge_item_id", "knowledge_item_id"),

        # ── Vector index (HNSW) ──────────────────────────────────────────────
        # NOT declared here. Must be added in the Alembic migration as raw SQL:
        #
        #   CREATE INDEX ix_kc_embedding_hnsw
        #   ON knowledge_chunks
        #   USING hnsw (embedding vector_cosine_ops)
        #   WITH (m = 16, ef_construction = 64);
        #
        # See: alembic/versions/004_create_knowledge_chunks.py
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeChunk item={str(self.knowledge_item_id)[:8]} "
            f"idx={self.chunk_index}>"
        )
