"""
知识库 ORM：库配置、文档入库状态机、分片与向量引用。

数据分工
--------
- ``DocumentChunk.content``：检索展示与 rerank 的**完整正文**（PG）
- 向量库 ``content_preview``：仅预览截断，供相似度检索与 hit 初筛
- ``VectorRef.vector_id``：Milvus/Weaviate/pgvector 外部主键，与 ``chunk_id`` 一对一

``Document.status`` 由 ``tenant.kb.services.ingest`` + Celery 驱动。
"""

import enum
import uuid

from sqlalchemy import Enum, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(str, enum.Enum):
    """入库流水线状态（PENDING → PARSING → EMBEDDING → READY）。"""

    PENDING = "pending"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    PARSE_FAILED = "parse_failed"
    EMBED_FAILED = "embed_failed"


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """检索配置：embedding/rerank 模型、chunk 参数、hybrid_alpha。"""

    __tablename__ = "kb_bases"
    __table_args__ = (Index("idx_kb_bases_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    embedding_model_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=768, nullable=False)
    visual_embedding_model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(16), default="vector", nullable=False)
    hybrid_alpha: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    rerank_model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rerank_candidate_k: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        foreign_keys="Document.kb_id",
        primaryjoin="KnowledgeBase.id == Document.kb_id",
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """原始文件元数据 + OSS 路径；celery_task_id 关联 TaskService 记录。"""

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
    """分片正文与 page_no；与 VectorRef 一对一。"""

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
    """chunk_id 与向量库 external_id 映射；vector_type 区分 text/image/audio。"""

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
