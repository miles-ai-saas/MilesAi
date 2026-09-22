"""
文档入库管道：Parse → Chunk → Embed → Index。

层级
----
- 本模块为 **L2 同步管道**（``run_ingest_pipeline``），不含文档状态机。
- Celery 任务、配额、失败重试在 ``miles_portal.tenant.kb.services.ingest`` 调用本管道。

顺序与一致性
------------
1. 从对象存储读字节（或接受预加载 ``raw`` / ``chunks``）→ 未传 chunks 时才 parse/chunk
2. 先 embedding（旧数据仍可检索）；再 ``on_before_index`` 清旧 → 写新分片/向量
3. 向量化（**唯一**调 embedding API 的环节）：文本走 ``embed_texts``；图片（CLIP 视觉 KB）
   走注入的 ``embed_visual_chunks`` 回调——按 KB 绑定的 CLIP 模型向量化图片字节
4. 全部分片：一次 flush 拿 chunk.id → ``gateway.upsert_chunk_vectors`` → 再写 ``VectorRef``

向量库侧不再重复 embedding（见 ``PrecomputedEmbeddings``）。
清旧后的空窗：embedding 完成后再清旧并写入，窗口仅覆盖写路径（不再跨厂商 HTTP）。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from miles_ai.rag.chunk import TextChunk, chunk_documents
from miles_ai.rag.index.gateway import ChunkVectorWrite, upsert_chunk_vectors
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
    load_bytes: LoadObjectBytes | None = None,
    raw: bytes | None = None,
    chunks: Sequence[TextChunk] | None = None,
    on_before_index: Callable[[Session, UUID], None] | None = None,
) -> IngestResult:
    """
    同步执行入库管道（不含文档状态机）。
    raw：预加载的原始文件字节（L1 可在会话外下载后传入）；与 load_bytes 须提供其一（视觉 embed 或未传 chunks 时）。
    chunks：L1 已 parse/chunk 时传入，避免 pipeline 重复解析。
    load_bytes：从对象存储读取原始文件（通常为 download_bytes）；未传 raw 且需要字节时必填。
    embed_visual_chunks：图片（CLIP 视觉 KB）入库时的视觉向量化回调，由 L1 注入。
    on_before_index：写入新分片前清理旧 chunk/向量（通常为 clear_document_derived_data_sync）。
    """
    parsed_chunks: list[TextChunk]
    file_bytes = raw
    if chunks is not None:
        parsed_chunks = list(chunks)
    else:
        if file_bytes is None:
            if load_bytes is None:
                raise ValueError("raw 与 load_bytes 须提供其一")
            file_bytes = load_bytes(data.object_key, data.object_bucket)
        docs = load_documents_from_bytes(file_bytes, data.filename, data.mime_type)
        parsed_chunks = chunk_documents(docs, data.chunk_size, data.chunk_overlap)
    if not parsed_chunks:
        raise ValueError("未能提取有效文本")

    chunks_text = [c.content for c in parsed_chunks]
    # 先 embedding：旧 chunk/向量仍可检索，缩短清旧后的空窗（仅覆盖写路径）
    if should_use_visual_image_embedding(kb, data.filename, data.mime_type):
        if embed_visual_chunks is None:
            raise ValueError("图片入库需注入 embed_visual_chunks（视觉向量化回调）")
        if file_bytes is None:
            if load_bytes is None:
                raise ValueError("视觉入库需要 raw 或 load_bytes")
            file_bytes = load_bytes(data.object_key, data.object_bucket)
        vectors = embed_visual_chunks(db, kb, file_bytes, len(chunks_text))
    else:
        vectors = embed_texts(db, kb, chunks_text)
    vector_type = vector_type_for_document(data.filename, data.mime_type)

    # 重试/覆盖入库：embedding 成功后再删旧，缩短检索空窗
    if on_before_index is not None:
        on_before_index(db, doc.id)

    # 批量：先 flush 全部分片拿 chunk.id，再一次 upsert 向量，最后写 VectorRef。
    # strict=True：embedding 服务返回数量与分片数不一致时必须报错，否则会静默漏写分片
    # （表现为「入库成功但部分内容检索不到」），比失败更难排查。
    # 向量批量失败则整批不写 VectorRef（依赖外层事务 rollback）。
    chunk_rows: list[DocumentChunk] = []
    for idx, (piece, _) in enumerate(zip(parsed_chunks, vectors, strict=True)):
        chunk = DocumentChunk(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
            chunk_index=idx,
            content=piece.content,
            page_no=piece.page_no,
        )
        db.add(chunk)
        chunk_rows.append(chunk)

    db.flush()

    writes = [
        ChunkVectorWrite(
            vector=vector,
            tenant_id=doc.tenant_id,
            kb_id=doc.kb_id,
            document_id=doc.id,
            chunk_id=chunk.id,
            content_preview=piece.content,
            object_key=data.object_key,
            page_no=piece.page_no,
        )
        for chunk, (piece, vector) in zip(chunk_rows, zip(parsed_chunks, vectors, strict=True), strict=True)
    ]
    ext_ids = upsert_chunk_vectors(writes)
    if len(ext_ids) != len(chunk_rows):
        raise ValueError(f"向量写入数量与分片不一致: {len(ext_ids)} != {len(chunk_rows)}")

    for chunk, ext_vector_id in zip(chunk_rows, ext_ids, strict=True):
        db.add(
            VectorRef(
                tenant_id=doc.tenant_id,
                chunk_id=chunk.id,
                vector_id=ext_vector_id,
                vector_type=vector_type,
            )
        )

    return IngestResult(chunks_text=chunks_text, chunk_count=len(chunks_text))
