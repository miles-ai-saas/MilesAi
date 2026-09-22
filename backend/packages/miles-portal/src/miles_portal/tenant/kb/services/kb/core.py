"""知识库 CRUD、配额与检索日志。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.kb import Document, KnowledgeBase
from miles_core.models.kb.search_log import KbSearchLog
from miles_core.models.model import ModelConfig
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_integrations.embeddings.model_meta import embedding_dimension_from_model
from miles_integrations.embeddings.policy import ensure_clip_model
from miles_portal.deletion.cascade import before_delete_kb
from miles_portal.tenant.kb.repositories.kb import KnowledgeBaseRepository
from miles_portal.tenant.kb.schemas.kb import (
    KbQuotaOut,
    KbSearchLogOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from miles_portal.tenant.kb.services.quota import assert_can_create_kb, get_kb_quota_out
from miles_portal.tenant.models.services.embedding_resolve import (
    get_default_embedding_model,
    resolve_embedding_model_by_id,
)
from miles_portal.tenant.models.services.rerank_resolve import resolve_rerank_model_by_id


class KnowledgeBaseCoreMixin:
    """知识库元数据、CRUD 与配额。"""

    db: AsyncSession
    ctx: TenantContext
    kb_repo: KnowledgeBaseRepository

    async def get_meta(self):
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        from miles_portal.tenant.kb.meta import kb_meta_dict
        from miles_portal.tenant.kb.schemas.meta import KbMetaOut

        return KbMetaOut.model_validate(kb_meta_dict())

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
        rerank_name = await self._model_name(kb.rerank_model_config_id) if kb.rerank_model_config_id else None
        visual_name = await self._model_name(kb.visual_embedding_model_config_id) if kb.visual_embedding_model_config_id else None
        return KnowledgeBaseOut(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            is_public=kb.is_public,
            embedding_model_config_id=kb.embedding_model_config_id,
            embedding_model_name=embed_name,
            embedding_dimension=kb.embedding_dimension,
            visual_embedding_model_config_id=kb.visual_embedding_model_config_id,
            visual_embedding_model_name=visual_name,
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

    async def list_search_logs(self, kb_id: UUID, params: PageParams) -> PageResult[KbSearchLogOut]:
        """分页列出该知识库的检索日志。"""
        await self._get_kb_or_raise(kb_id)
        from miles_core.pagination import paginate

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
        visual_model_id = body.visual_embedding_model_config_id
        if visual_model_id:
            visual_model = await resolve_embedding_model_by_id(self.db, visual_model_id, self.ctx.tenant_id)
            ensure_clip_model(visual_model)
        kb = await self.kb_repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            is_public=body.is_public,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
            embedding_model_config_id=model.id,
            embedding_dimension=dimension,
            visual_embedding_model_config_id=visual_model_id,
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
        if "visual_embedding_model_config_id" in data:
            visual_id = data.get("visual_embedding_model_config_id")
            if visual_id:
                visual_model = await resolve_embedding_model_by_id(self.db, visual_id, self.ctx.tenant_id)
                ensure_clip_model(visual_model)
            else:
                data["visual_embedding_model_config_id"] = None
        await self.kb_repo.update_fields(kb, data)
        await self.db.refresh(kb)
        return await self._to_kb_out(kb)

    async def delete_kb(self, kb_id: UUID) -> None:
        """
        删除知识库：逐文档清理衍生数据与 OSS，解绑 Agent/市场引用后软删 KB。

        向量库按 document_id 删除；不单独按 kb_id 扫全库（依赖文档级清理）。
        """
        kb = await self._get_kb_or_raise(kb_id)
        docs = (await self.db.execute(select(Document).where(Document.kb_id == kb.id, not_deleted(Document)))).scalars().all()
        for doc in docs:
            await self.delete_document(kb_id, doc.id)
        await before_delete_kb(self.db, kb.id)
        await mark_deleted(self.db, kb)
