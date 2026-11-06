import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.providers.base import EMBEDDING_DIM
from app.database.session import Base


class DocumentChunk(Base):
    """Retrieval unit (PRD D5). heading_path is the section reference; its first element is the chapter."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_document_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_document_chunks_hash_model", "content_hash", "embedding_model"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    # Denormalized from the document so retrieval filters without a join.
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), index=True)
    # Most similar syllabus topic (embedding match within the document's course), or None.
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    ordinal: Mapped[int]
    heading_path: Mapped[str] = mapped_column(Text, default="")
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    content_type: Mapped[str] = mapped_column(String(10))  # text | table | mixed
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the embedded text: embedding cache key
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str] = mapped_column(String(100))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', heading_path || ' ' || content)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
