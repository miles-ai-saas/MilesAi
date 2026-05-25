"""
知识库 L1 用例：CRUD、上传、检索、删除编排。

上传（异步）
------------
校验配额/类型 → 写 OSS → 建 ``Document(PENDING)`` → ``ingest_document.delay``
→ Worker ``run_ingest`` → ``rag.pipeline``（详见各层模块注释）。

检索（同步 HTTP）
-----------------
``embed_query_for_kb`` → ``search_kb_chunks`` → 从 PG 取 **完整** chunk.content 组装响应
（向量库 hit 仅含 content_preview 截断）。

删除
----
``clear_document_derived_data_async``（PG 分片 + vector_ref + 向量库）→ 删 OSS → 软删文档。

约束
----
``embedding_model_config_id`` / ``embedding_dimension`` 在 **创建 KB 时固化**，后续不可改。
"""

import time
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.embeddings.runtime import embedding_dimension_from_model
from app.integrations.langchain.embeddings import embed_query_for_kb
from app.core.config import get_settings
from app.common.exceptions import BadRequestError, NotFoundError
from app.infra.storage import build_object_key, delete_object, upload_bytes
from app.rag.retrieve import resolve_retrieval_mode, search_kb_chunks
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.deletion.cascade import before_delete_kb
from app.deletion.document import clear_document_derived_data_async
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase
from app.models.model import ModelConfig
from app.tenant.kb.repositories.kb import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    VectorRefRepository,
)
from app.common.schema import PageParams, PageResult
from app.tenant.models.services.embedding_resolve import (
    get_default_embedding_model,
    resolve_embedding_model_by_id,
)
from app.tenant.models.services.rerank_resolve import resolve_rerank_model_by_id
from app.tenant.kb.schemas.kb import (
    DocumentChunkOut,
    DocumentOut,
    KbQuotaOut,
    KbSearchLogOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.tenant.kb.services.quota import (
    apply_storage_delta,
    assert_can_create_kb,
    assert_can_upload_bytes,
    get_kb_quota_out,
)
from app.tenant.kb.services.search_log import write_kb_search_log
from app.models.kb_search_log import KbSearchLog
from app.rag.parse import file_extension, is_audio_file, is_image_file
from app.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService

settings = get_settings()

class KnowledgeBaseService(BaseService):
    """上传后仅落 OSS + 建 Document 行并投递 Celery；解析索引见 rag.pipeline。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """注入异步 DB 会话与租户上下文。"""
        super().__init__(db, ctx)
        self.kb_repo = KnowledgeBaseRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = DocumentChunkRepository(db)
        self.vector_repo = VectorRefRepository(db)

    async def _get_kb_or_raise(self, kb_id: UUID) -> KnowledgeBase:
        """加载 KB 并校验租户与未删除。"""
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb or is_marked_deleted(kb):
            raise NotFoundError("知识库不存在")
        assert_tenant_access(self.ctx, kb.tenant_id)
        return kb

    async def _model_name(self, model_id: UUID) -> str | None:
        """解析模型配置 ID 对应的展示名。"""
        row = await self.db.get(ModelConfig, model_id)
        return row.name if row else None

    async def _to_kb_out(self, kb: KnowledgeBase) -> KnowledgeBaseOut:
        """ORM → API 出参，附带 embedding/rerank 模型名。"""
        embed_name = await self._model_name(kb.embedding_model_config_id)
        rerank_name = (
            await self._model_name(kb.rerank_model_config_id)
            if kb.rerank_model_config_id
            else None
        )
        return KnowledgeBaseOut(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            is_public=kb.is_public,
            embedding_model_config_id=kb.embedding_model_config_id,
            embedding_model_name=embed_name,
            embedding_dimension=kb.embedding_dimension,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            retrieval_mode=kb.retrieval_mode,
            hybrid_alpha=kb.hybrid_alpha,
            rerank_model_config_id=kb.rerank_model_config_id,
            rerank_model_name=rerank_name,
            rerank_candidate_k=kb.rerank_candidate_k,
            created_at=kb.created_at,
        )

    async def list_kbs(self, params: PageParams) -> PageResult[KnowledgeBaseOut]:
        """分页列出当前租户知识库。"""
        filters = tenant_filters(self.ctx, KnowledgeBase.tenant_id)
        page = await self.kb_repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=KnowledgeBase.created_at.desc(),
        )
        items = [await self._to_kb_out(k) for k in page.items]
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def get_quota(self) -> KbQuotaOut:
        """返回租户 KB 配额使用情况。"""
        data = await get_kb_quota_out(self.db, self.ctx.tenant_id)
        return KbQuotaOut(**data)

    async def list_search_logs(
        self, kb_id: UUID, params: PageParams
    ) -> PageResult[KbSearchLogOut]:
        """分页列出该知识库的检索日志。"""
        await self._get_kb_or_raise(kb_id)
        from app.common.pagination import paginate

        page = await paginate(
            self.db,
            KbSearchLog,
            page=params.page,
            size=params.size,
            filters=[
                KbSearchLog.tenant_id == self.ctx.tenant_id,
                KbSearchLog.kb_id == kb_id,
            ],
            order_by=KbSearchLog.created_at.desc(),
            skip_soft_delete_filter=True,
        )
        items = [KbSearchLogOut.model_validate(r) for r in page.items]
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_kb(self, body: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        """创建 KB：解析 embedding 维度，可选校验 rerank 模型。"""
        await assert_can_create_kb(self.db, self.ctx.tenant_id)
        model_id = body.embedding_model_config_id
        if not model_id:
            model_id = (await get_default_embedding_model(self.db)).id
        model = await resolve_embedding_model_by_id(self.db, model_id, self.ctx.tenant_id)
        dimension = embedding_dimension_from_model(model)
        rerank_model_id = body.rerank_model_config_id
        if rerank_model_id:
            await resolve_rerank_model_by_id(self.db, rerank_model_id, self.ctx.tenant_id)
        kb = await self.kb_repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            is_public=body.is_public,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
            embedding_model_config_id=model.id,
            embedding_dimension=dimension,
            rerank_model_config_id=rerank_model_id,
            rerank_candidate_k=body.rerank_candidate_k,
        )
        await self.db.refresh(kb)
        return await self._to_kb_out(kb)

    async def get_kb(self, kb_id: UUID) -> KnowledgeBaseOut:
        """按 ID 获取知识库详情。"""
        kb = await self._get_kb_or_raise(kb_id)
        return await self._to_kb_out(kb)

    async def update_kb(self, kb_id: UUID, body: KnowledgeBaseUpdate) -> KnowledgeBaseOut:
        """部分更新 KB 字段（rerank 配置变更时校验模型存在）。"""
        kb = await self._get_kb_or_raise(kb_id)
        data = body.model_dump(exclude_unset=True)
        rerank_id = data.get("rerank_model_config_id")
        if rerank_id:
            await resolve_rerank_model_by_id(self.db, rerank_id, self.ctx.tenant_id)
        elif "rerank_model_config_id" in data and data["rerank_model_config_id"] is None:
            data["rerank_model_config_id"] = None
        await self.kb_repo.update_fields(kb, data)
        await self.db.refresh(kb)
        return await self._to_kb_out(kb)

    async def delete_kb(self, kb_id: UUID) -> None:
        """
        删除知识库：逐文档清理衍生数据与 OSS，解绑 Agent/市场引用后软删 KB。

        向量库按 document_id 删除；不单独按 kb_id 扫全库（依赖文档级清理）。
        """
        kb = await self._get_kb_or_raise(kb_id)
        docs = (
            await self.db.execute(
                select(Document).where(Document.kb_id == kb.id, not_deleted(Document))
            )
        ).scalars().all()
        for doc in docs:
            await self.delete_document(kb_id, doc.id)
        await before_delete_kb(self.db, kb.id)
        await mark_deleted(self.db, kb)

    async def list_documents(self, kb_id: UUID, params: PageParams) -> PageResult[DocumentOut]:
        """分页列出文档；READY 文档附带分片数量。"""
        await self._get_kb_or_raise(kb_id)
        page = await self.doc_repo.list_page(
            page=params.page,
            size=params.size,
            filters=[Document.kb_id == kb_id],
            order_by=Document.created_at.desc(),
        )
        ready_ids = [d.id for d in page.items if d.status == DocumentStatus.READY]
        chunk_counts = await self.chunk_repo.count_by_document_ids(ready_ids)
        items = []
        for doc in page.items:
            out = DocumentOut.model_validate(doc)
            count = chunk_counts.get(doc.id) if doc.status == DocumentStatus.READY else None
            items.append(out.model_copy(update={"chunk_count": count}))
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def list_document_chunks(
        self,
        kb_id: UUID,
        document_id: UUID,
        params: PageParams,
    ) -> PageResult[DocumentChunkOut]:
        """分页列出文档在 PG 中的分片正文（chunk_index 升序）。"""
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        assert_tenant_access(self.ctx, doc.tenant_id)
        page = await self.chunk_repo.list_page(
            page=params.page,
            size=params.size,
            filters=[
                DocumentChunk.document_id == document_id,
                DocumentChunk.kb_id == kb_id,
            ],
            order_by=DocumentChunk.chunk_index.asc(),
        )
        return PageResult(
            items=[DocumentChunkOut.model_validate(c) for c in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def upload_document(
        self,
        kb_id: UUID,
        file: UploadFile,
    ) -> DocumentOut:
        """校验类型与配额 → OSS → 建 Document → 投递 Celery ingest。"""
        kb = await self._get_kb_or_raise(kb_id)
        if not file.filename:
            raise BadRequestError("文件名不能为空")
        content = await file.read()
        await assert_can_upload_bytes(self.db, kb.tenant_id, len(content))
        mime = file.content_type or "application/octet-stream"
        if not is_kb_upload_allowed(file.filename, mime):
            raise BadRequestError(
                f"不支持的文件类型: {mime}。{kb_upload_allowed_hint()}"
            )

        doc = await self.doc_repo.create(
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            object_bucket=settings.object_storage_bucket,
            object_key="pending",
            status=DocumentStatus.PENDING,
        )
        object_key = build_object_key(
            str(kb.tenant_id), str(kb.id), str(doc.id), file.filename
        )
        doc.object_key = object_key
        upload_bytes(content, object_key, mime)
        await self.db.flush()

        # 异步 ingest；失败状态见 doc.status / fail_reason
        from app.workers.tasks.ingest import ingest_document
        from app.tenant.tasks.services.task import TaskService

        task = ingest_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name="ingest_document",
            resource_type="document",
            resource_id=doc.id,
        )
        await apply_storage_delta(self.db, kb.tenant_id, len(content))
        await self.db.flush()
        await self.db.refresh(doc)
        return DocumentOut.model_validate(doc)

    async def retry_document(self, kb_id: UUID, document_id: UUID) -> DocumentOut:
        """失败或已完成文档重新入库（pipeline 内会先清旧分片/向量）。"""
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        if doc.status not in (
            DocumentStatus.PARSE_FAILED,
            DocumentStatus.EMBED_FAILED,
            DocumentStatus.READY,
        ):
            raise BadRequestError("仅失败或已完成的文档可重新入库")
        if not doc.object_key or doc.object_key == "pending":
            raise BadRequestError("文档文件不可用，请重新上传")

        from app.workers.tasks.ingest import ingest_document
        from app.tenant.tasks.services.task import TaskService

        doc.status = DocumentStatus.PENDING
        doc.fail_reason = None
        task = ingest_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name="ingest_document",
            resource_type="document",
            resource_id=doc.id,
        )
        await self.db.flush()
        await self.db.refresh(doc)
        return DocumentOut.model_validate(doc)

    async def delete_document(self, kb_id: UUID, document_id: UUID) -> None:
        """删除衍生数据、OSS 对象并软删文档行。"""
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        # 先清 PG 分片与向量库，再删 OSS、软删文档行
        await clear_document_derived_data_async(self.db, doc.id)
        if doc.object_key and doc.object_key != "pending":
            try:
                delete_object(doc.object_key, doc.object_bucket)
            except Exception:
                pass
        size = doc.file_size or 0
        await mark_deleted(self.db, doc)
        if size > 0:
            await apply_storage_delta(self.db, doc.tenant_id, 0)

    async def search(self, kb_id: UUID, body: SearchRequest) -> SearchResponse:
        """
        工作台 KB 检索 API。

        召回走 ``search_kb_chunks``（与 Agent 共用 L2 逻辑）；
        展示用正文来自 PG ``document_chunks``，非向量库 preview 字段。
        """
        kb = await self._get_kb_or_raise(kb_id)
        effective_mode = resolve_retrieval_mode(kb, body.mode)
        started = time.perf_counter()
        vector = await embed_query_for_kb(self.db, self.ctx.tenant_id, kb, body.query)
        rerank_model = None
        if kb.rerank_model_config_id:
            rerank_model = await resolve_rerank_model_by_id(
                self.db, kb.rerank_model_config_id, self.ctx.tenant_id
            )
        raw_hits = await search_kb_chunks(
            self.db,
            kb=kb,
            query=body.query,
            query_vector=vector,
            limit=body.top_k,
            mode=body.mode,
            rerank_model=rerank_model,
        )
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
                )
            )
        log_mode = effective_mode
        if rerank_model is not None:
            log_mode = f"{effective_mode}+rerank"
        latency_ms = int((time.perf_counter() - started) * 1000)
        await write_kb_search_log(
            self.db,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            query=body.query,
            top_k=body.top_k,
            hit_count=len(hits),
            latency_ms=latency_ms,
            source="api",
            actor_user_id=self.ctx.user_id,
            retrieval_mode=log_mode,
        )
        return SearchResponse(query=body.query, mode=log_mode, hits=hits)
