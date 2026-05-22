import enum
import uuid

from sqlalchemy import Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    PARSE_FAILED = "parse_failed"
    EMBED_FAILED = "embed_failed"


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kb_bases"
    __table_args__ = (Index("idx_kb_bases_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    embedding_profile: Mapped[str] = mapped_column(String(64), default="local-minilm", nullable=False)
    embedding_backend: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    embedding_model_name: Mapped[str] = mapped_column(
        String(256), default="sentence-transformers/all-MiniLM-L6-v2", nullable=False
    )
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=384, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        foreign_keys="Document.kb_id",
        primaryjoin="KnowledgeBase.id == Document.kb_id",
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kb_documents"
    __table_args__ = (
        Index("idx_kb_documents_tenant_id", "tenant_id"),
        Index("idx_kb_documents_kb_id", "kb_id"),
        Index("un_kb_documents_tenant_id_kb_id", "tenant_id", "kb_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    object_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="documents",
        foreign_keys=[kb_id],
        primaryjoin="Document.kb_id == KnowledgeBase.id",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        foreign_keys="DocumentChunk.document_id",
        primaryjoin="Document.id == DocumentChunk.document_id",
    )


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kb_document_chunks"
    __table_args__ = (
        Index("idx_kb_document_chunks_tenant_id", "tenant_id"),
        Index("idx_kb_document_chunks_document_id", "document_id"),
        Index("idx_kb_document_chunks_kb_id", "kb_id"),
        Index("un_kb_document_chunks_document_id_chunk_index", "document_id", "chunk_index"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
        foreign_keys=[document_id],
        primaryjoin="DocumentChunk.document_id == Document.id",
    )
    vector_ref: Mapped["VectorRef | None"] = relationship(
        "VectorRef",
        back_populates="chunk",
        uselist=False,
        foreign_keys="VectorRef.chunk_id",
        primaryjoin="DocumentChunk.id == VectorRef.chunk_id",
    )


class VectorRef(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kb_vector_refs"
    __table_args__ = (
        Index("idx_kb_vector_refs_tenant_id", "tenant_id"),
        UniqueConstraint("chunk_id", name="uk_kb_vector_refs_chunk_id"),
        Index("idx_kb_vector_refs_vector_id", "vector_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)

    chunk: Mapped["DocumentChunk"] = relationship(
        "DocumentChunk",
        back_populates="vector_ref",
        foreign_keys=[chunk_id],
        primaryjoin="VectorRef.chunk_id == DocumentChunk.id",
    )
