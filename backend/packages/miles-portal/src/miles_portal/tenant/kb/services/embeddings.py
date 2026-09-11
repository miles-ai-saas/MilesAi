"""知识库向量化（L1 kb 域）：按 KB 绑定模型解析后调用 L3 provider。

分层
----
- 本模块为 **L1 装配层**：按 ``kb.embedding_model_config_id`` / 视觉模型 id
  resolve ``ModelConfig``（含 BYOK 合并），再调用 L3 纯编排
  ``integrations.embeddings.runtime.build_embeddings`` / CLIP provider。
- L3 ``integrations/langchain/embeddings.py`` 不再承载这些解析（B-2b 后仅存纯层）。
- ``build_kb_retrieval_bindings`` 构造供 L3 ``vectorstores`` 检索注入的中立载体。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_common.exceptions import BadRequestError
from miles_ai.integrations.embeddings.constants import INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.registry import get_embedding_provider
from miles_ai.integrations.embeddings.runtime import build_embeddings
from miles_ai.integrations.langchain.kb_retrieval import KbRetrievalBindings
from miles_portal.tenant.models.services.embedding_resolve import (
    resolve_embedding_model_by_id,
    resolve_embedding_model_sync,
)

if TYPE_CHECKING:
    from miles_core.models.kb import KnowledgeBase


def embed_texts_for_kb_sync(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """同步批量向量化分片文本（Celery 入库 pipeline 注入）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_documents(texts)


def embed_query_for_kb_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    """同步 query 向量化（内置工具/脚本路径）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_query(query)


async def embed_query_for_kb(db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, query: str) -> list[float]:
    """异步 query 向量化（工作台 KB 检索 API 与 Agent async 检索）。"""
    model = await resolve_embedding_model_by_id(db, kb.embedding_model_config_id, tenant_id)
    return build_embeddings(model).embed_query(query)


def _ensure_clip(model) -> None:
    """视觉模型必须为 CLIP（复用 L3 纯校验，避免重复实现）。"""
    from miles_ai.integrations.langchain.visual_embeddings import ensure_clip_model

    ensure_clip_model(model)


def embed_image_chunks_vectors_sync(
    db: Session,
    kb: KnowledgeBase,
    raw: bytes,
    chunk_count: int,
) -> list[list[float]]:
    """同步图片向量化：单图向量复制到每个分片（入库 pipeline 注入）。"""
    vec = _embed_image_bytes_sync(db, kb, raw)
    return [vec] * chunk_count


def _embed_image_bytes_sync(db: Session, kb: KnowledgeBase, raw: bytes) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = resolve_embedding_model_sync(db, kb.visual_embedding_model_config_id, kb.tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]


async def embed_query_visual_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    query: str,
) -> list[float]:
    """异步视觉文本搜图 query 向量化（工作台 KB API）。"""
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    text = (query or "").strip()
    if not text:
        raise BadRequestError("视觉文本搜图需填写 query")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_texts(model, [text])[0]


async def embed_image_bytes_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    raw: bytes,
) -> list[float]:
    """异步以图搜图 query_document_id 的图片向量化（工作台 KB API）。"""
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]


def build_kb_retrieval_bindings() -> KbRetrievalBindings:
    """构造 L3 ``vectorstores`` 检索注入的 KB 检索能力载体。"""
    return KbRetrievalBindings(
        embed_query_sync=embed_query_for_kb_sync,
        resolve_rerank_sync=_resolve_rerank_sync,
        embed_query=embed_query_for_kb,
        resolve_rerank=_resolve_rerank_async,
    )


def _resolve_rerank_sync(db: Session, kb: KnowledgeBase, tenant_id: UUID):
    """解析 KB 绑定的 rerank 模型；未配置返回 None（L3 multi_kb 注入形参）。"""
    if not kb.rerank_model_config_id:
        return None
    from miles_portal.tenant.models.services.rerank_resolve import resolve_rerank_model_sync

    return resolve_rerank_model_sync(db, kb.rerank_model_config_id, tenant_id)


async def _resolve_rerank_async(db: AsyncSession, kb: KnowledgeBase, tenant_id: UUID):
    """异步解析 rerank 模型（multi_kb_async 使用）。"""
    if not kb.rerank_model_config_id:
        return None
    from miles_portal.tenant.models.services.rerank_resolve import resolve_rerank_model_by_id

    return await resolve_rerank_model_by_id(db, kb.rerank_model_config_id, tenant_id)
