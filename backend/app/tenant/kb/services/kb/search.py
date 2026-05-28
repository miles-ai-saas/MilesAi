"""知识库检索（文本 / 视觉 / 混合）。"""

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.infra.storage.resolve import resolve_object_storage_async
from app.integrations.langchain.embeddings import embed_query_for_kb
from app.integrations.langchain.visual_embeddings import (
    embed_image_bytes_async,
    embed_query_visual_async,
)
from app.models.kb import DocumentStatus, KnowledgeBase
from app.rag.parse import is_image_file, is_video_file
from app.rag.parse.image_parser import parse_image
from app.rag.parse.video_parser import parse_video
from app.rag.retrieve import resolve_retrieval_mode, search_kb_chunks
from app.rag.retrieve.media_filter import filter_hits_by_media_types_async
from app.tenant.kb.repositories.kb import DocumentChunkRepository, DocumentRepository
from app.tenant.kb.schemas.kb import SearchHit, SearchRequest, SearchResponse
from app.tenant.kb.services.search_log import write_kb_search_log
from app.tenant.models.services.rerank_resolve import resolve_rerank_model_by_id


class KnowledgeBaseSearchMixin:
    """工作台 KB 检索 API（与 Agent 共用 L2 召回逻辑）。"""

    db: AsyncSession
    ctx: TenantContext
    doc_repo: DocumentRepository
    chunk_repo: DocumentChunkRepository

    async def _resolve_search_query(
        self,
        kb_id: UUID,
        body: SearchRequest,
    ) -> tuple[str, list[str] | None]:
        """组合文本 query 与 query_document_id（OCR/转写）并推断 media_types 过滤。"""
        query = (body.query or "").strip()
        media_types = list(body.media_types) if body.media_types else None

        if body.query_document_id is None:
            if not query:
                raise BadRequestError("检索 query 不能为空")
            return query, media_types

        doc = await self.doc_repo.get_by_id_or_raise(body.query_document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        assert_tenant_access(self.ctx, doc.tenant_id)
        if doc.status != DocumentStatus.READY:
            raise BadRequestError("query_document_id 须为已就绪（ready）的文档")

        if not doc.object_key or doc.object_key == "pending":
            raise BadRequestError("文档对象尚未就绪")

        storage = await resolve_object_storage_async(doc.tenant_id, self.db)
        data = storage.storage.download_bytes(doc.object_key, bucket=doc.object_bucket)
        if is_image_file(doc.filename, doc.mime_type):
            derived = parse_image(data, doc.filename)
            if media_types is None:
                media_types = ["image"]
        elif is_video_file(doc.filename, doc.mime_type) or doc.mime_type.startswith("video/"):
            derived = parse_video(data, doc.filename)
            if media_types is None:
                media_types = ["video"]
        else:
            raise BadRequestError("query_document_id 仅支持图片或视频文档")

        derived = (derived or "").strip()
        if not derived or derived.startswith("[图片 ·") or derived.startswith("[视频 ·"):
            raise BadRequestError("未能从 query_document_id 提取有效文本，请安装 OCR/Whisper/ffmpeg 或改用手动 query")

        combined = f"{query}\n\n{derived}".strip() if query else derived
        return combined, media_types

    async def _search_visual(
        self,
        kb: KnowledgeBase,
        body: SearchRequest,
    ) -> tuple[str, list[float], list[str] | None]:
        """CLIP 视觉检索：文本搜图或以 query_document_id 图片 embedding 搜图。"""
        if not kb.visual_embedding_model_config_id:
            raise BadRequestError("知识库未配置 CLIP 视觉向量化模型")
        media_types = list(body.media_types) if body.media_types else ["image"]
        query = (body.query or "").strip()

        if body.query_document_id is not None:
            doc = await self.doc_repo.get_by_id_or_raise(body.query_document_id, label="文档不存在")
            if doc.kb_id != kb.id or is_marked_deleted(doc):
                raise NotFoundError("文档不存在")
            assert_tenant_access(self.ctx, doc.tenant_id)
            if doc.status != DocumentStatus.READY:
                raise BadRequestError("query_document_id 须为已就绪（ready）的文档")
            if not is_image_file(doc.filename, doc.mime_type):
                raise BadRequestError("视觉以图搜图仅支持图片文档")
            storage = await resolve_object_storage_async(doc.tenant_id, self.db)
            data = storage.storage.download_bytes(doc.object_key, bucket=doc.object_bucket)
            vector = await embed_image_bytes_async(self.db, self.ctx.tenant_id, kb, data)
            query_text = query or f"[CLIP 以图搜图] {doc.filename}"
            return query_text, vector, media_types

        if not query:
            raise BadRequestError("视觉文本搜图需填写 query")
        vector = await embed_query_visual_async(self.db, self.ctx.tenant_id, kb, query)
        return query, vector, media_types

    async def search(self, kb_id: UUID, body: SearchRequest) -> SearchResponse:
        """
        工作台 KB 检索 API。

        召回走 ``search_kb_chunks``（与 Agent 共用 L2 逻辑）；
        展示用正文来自 PG ``document_chunks``，非向量库 preview 字段。
        """
        kb = await self._get_kb_or_raise(kb_id)
        effective_mode = resolve_retrieval_mode(kb, body.mode)
        started = time.perf_counter()

        if body.visual_search:
            query_text, vector, media_types = await self._search_visual(kb, body)
            effective_mode = "vector"
            rerank_model = None
        else:
            query_text, media_types = await self._resolve_search_query(kb_id, body)
            vector = await embed_query_for_kb(self.db, self.ctx.tenant_id, kb, query_text)
            rerank_model = None
            if kb.rerank_model_config_id:
                rerank_model = await resolve_rerank_model_by_id(self.db, kb.rerank_model_config_id, self.ctx.tenant_id)

        fetch_limit = body.top_k
        if media_types:
            fetch_limit = max(body.top_k * 3, kb.rerank_candidate_k or 50)
        raw_hits = await search_kb_chunks(
            self.db,
            kb=kb,
            query=query_text,
            query_vector=vector,
            limit=fetch_limit,
            mode=effective_mode if not body.visual_search else "vector",
            rerank_model=None if media_types or body.visual_search else rerank_model,
        )
        raw_hits = await filter_hits_by_media_types_async(self.db, raw_hits, media_types)
        if rerank_model is not None and media_types and not body.visual_search:
            from app.rag.retrieve.rerank import apply_rerank_to_hits

            raw_hits = apply_rerank_to_hits(
                raw_hits,
                query=query_text,
                rerank_model=rerank_model,
                top_n=body.top_k,
            )
        else:
            raw_hits = raw_hits[: body.top_k]
        hits: list[SearchHit] = []
        for h in raw_hits:
            chunk_id = h.get("chunk_id")
            if not chunk_id:
                continue
            chunk = await self.chunk_repo.get_by_id(UUID(chunk_id))
            if not chunk:
                continue
            doc = await self.doc_repo.get_by_id(UUID(h["document_id"]))
            if not doc or is_marked_deleted(doc):
                continue
            hits.append(
                SearchHit(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=float(h.get("score", 0)),
                    score_vector=h.get("score_vector"),
                    score_keyword=h.get("score_keyword"),
                    score_rerank=h.get("score_rerank"),
                    filename=doc.filename if doc else None,
                    vector_type=h.get("vector_type"),
                    mime_type=doc.mime_type if doc else None,
                )
            )
        log_mode = "visual" if body.visual_search else effective_mode
        if rerank_model is not None:
            log_mode = f"{log_mode}+rerank"
        if media_types:
            log_mode = f"{log_mode}+media:{','.join(media_types)}"
        latency_ms = int((time.perf_counter() - started) * 1000)
        await write_kb_search_log(
            self.db,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            query=query_text,
            top_k=body.top_k,
            hit_count=len(hits),
            latency_ms=latency_ms,
            source="api",
            actor_user_id=self.ctx.user_id,
            retrieval_mode=log_mode,
        )
        return SearchResponse(query=query_text, mode=log_mode, hits=hits)
