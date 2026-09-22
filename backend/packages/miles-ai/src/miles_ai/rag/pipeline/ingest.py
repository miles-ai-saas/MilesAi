"""
文档入库管道：Parse → Chunk → Embed → Index。

层级
----
- 本模块为 **L2 同步管道**（``run_ingest_pipeline``），不含文档状态机。
- Celery 任务、配额、失败重试在 ``miles_portal.tenant.kb.services.ingest`` 调用本管道。

顺序与一致性
------------
1. 从对象存储读字节 → ``load_documents_from_bytes``（按 mime/扩展名选 parser）
2. ``chunk_documents`` 分片（chunk_size/overlap 来自 KB）
3. 可选 ``on_before_index``：删旧 PG chunk、vector_ref 及向量库记录（覆盖入库）
4. 向量化（**唯一**调 embedding API 的环节）：文本走 ``embed_texts``；图片（CLIP 视觉 KB）
   走注入的 ``embed_visual_chunks`` 回调——按 KB 绑定的 CLIP 模型向量化图片字节
5. 每个分片：**先 flush PG 拿 chunk.id** → ``gateway.upsert_chunk_vector`` → 写 ``VectorRef``

向量库侧不再重复 embedding（见 ``PrecomputedEmbeddings``）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from miles_ai.rag.chunk import chunk_documents
from miles_ai.rag.index.gateway import upsert_chunk_vector
from miles_ai.rag.parse import vector_type_for_document
from miles_ai.rag.parse.loaders import load_documents_from_bytes
from miles_ai.rag.pipeline.visual_policy import should_use_visual_image_embedding
from miles_core.models.kb import Document, DocumentChunk, KnowledgeBase, VectorRef


class EmbedTextsForKb(Protocol):
    """按 KB 绑定的 embedding 模型批量向量化分片文本。"""

    def __call__(self, db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]: ...


class EmbedVisualChunks(Protocol):
    """按 KB 绑定的 CLIP 模型向量化图片字节（每分片一份向量）。"""

    def __call__(self, db: Session, kb: KnowledgeBase, raw: bytes, chunk_count: int) -> list[list[float]]: ...


class LoadObjectBytes(Protocol):
    """从对象存储读取原始文件字节。"""

    def __call__(self, object_key: str, object_bucket: str) -> bytes: ...


@dataclass(frozen=True)
class IngestInput:
    """入库管道输入：文件元数据与分片参数。"""

    filename: str  # 原始文件名
    mime_type: str  # MIME 类型
    object_key: str  # 对象存储 key
    object_bucket: str  # 对象存储桶名
    chunk_size: int  # 分片大小（字符）
    chunk_overlap: int  # 分片重叠（字符）


@dataclass
class IngestResult:
    """入库管道输出摘要（不含状态机）。"""

    chunks_text: list[str]  # 各分片文本
    chunk_count: int  # 分片数量


def run_ingest_pipeline(
    db: Session,
    *,
    doc: Document,
    kb: KnowledgeBase,
    data: IngestInput,
    embed_texts: EmbedTextsForKb,
    embed_visual_chunks: EmbedVisualChunks | None = None,
    load_bytes: LoadObjectBytes,
    on_before_index: Callable[[Session, UUID], None] | None = None,
) -> IngestResult:
    """
    同步执行入库管道（不含文档状态机）。
    load_bytes：从对象存储读取原始文件（通常为 download_bytes）。
    embed_visual_chunks：图片（CLIP 视觉 KB）入库时的视觉向量化回调，由 L1 注入。
    on_before_index：写入新分片前清理旧 chunk/向量（通常为 clear_document_derived_data_sync）。
    """
    raw = load_bytes(data.object_key, data.object_bucket)
    docs = load_documents_from_bytes(raw, data.filename, data.mime_type)
    chunks = chunk_documents(docs, data.chunk_size, data.chunk_overlap)
    if not chunks:
        raise ValueError("未能提取有效文本")

    # 重试/覆盖入库：先删旧 chunk、vector_ref 与向量库记录
    if on_before_index is not None:
        on_before_index(db, doc.id)

    chunks_text = [c.content for c in chunks]
    if should_use_visual_image_embedding(kb, data.filename, data.mime_type):
        if embed_visual_chunks is None:
            raise ValueError("图片入库需注入 embed_visual_chunks（视觉向量化回调）")
        vectors = embed_visual_chunks(db, kb, raw, len(chunks_text))
    else:
        vectors = embed_texts(db, kb, chunks_text)
    vector_type = vector_type_for_document(data.filename, data.mime_type)

    # 逐分片事务：chunk.id 作为 Milvus/Weaviate 主键与 vector_ref 外键。
    # strict=True：embedding 服务返回数量与分片数不一致时必须报错，否则会静默漏写分片
    # （表现为「入库成功但部分内容检索不到」），比失败更难排查。
    for idx, (piece, vector) in enumerate(zip(chunks, vectors, strict=True)):
        chunk = DocumentChunk(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
            chunk_index=idx,
            content=piece.content,
            page_no=piece.page_no,
        )
        db.add(chunk)
        db.flush()  # 需要 chunk.id 再写向量库

        ext_vector_id = upsert_chunk_vector(
            vector=vector,
            tenant_id=doc.tenant_id,
            kb_id=doc.kb_id,
            document_id=doc.id,
            chunk_id=chunk.id,
            content_preview=piece.content,
            object_key=data.object_key,
            page_no=piece.page_no,
        )
        db.add(
            VectorRef(
                tenant_id=doc.tenant_id,
                chunk_id=chunk.id,
                vector_id=ext_vector_id,
                vector_type=vector_type,
            )
        )

    return IngestResult(chunks_text=chunks_text, chunk_count=len(chunks_text))
