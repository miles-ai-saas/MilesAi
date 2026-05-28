"""知识库 CLIP 视觉向量化（入库图片 / 视觉检索 query）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.constants import INVOKE_MODE_CLIP
from app.integrations.embeddings.model_meta import invoke_mode_from_model
from app.integrations.embeddings.registry import get_embedding_provider
from app.models.kb import KnowledgeBase
from app.rag.parse.media import is_image_file
from app.tenant.models.services.embedding_resolve import (
    resolve_embedding_model_by_id,
    resolve_embedding_model_sync,
)


def ensure_clip_model(model) -> None:
    if invoke_mode_from_model(model) != INVOKE_MODE_CLIP:
        raise BadRequestError(f"模型「{model.name}」不是 CLIP 视觉向量化模型")


def should_use_visual_image_embedding(
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
) -> bool:
    return kb.visual_embedding_model_config_id is not None and is_image_file(filename, mime_type)


def embed_image_bytes_sync(db: Session, kb: KnowledgeBase, raw: bytes) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = resolve_embedding_model_sync(db, kb.visual_embedding_model_config_id, kb.tenant_id)
    ensure_clip_model(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]


def embed_image_chunks_vectors_sync(
    db: Session,
    kb: KnowledgeBase,
    raw: bytes,
    chunk_count: int,
) -> list[list[float]]:
    vec = embed_image_bytes_sync(db, kb, raw)
    return [vec] * chunk_count


def embed_query_visual_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    text = (query or "").strip()
    if not text:
        raise BadRequestError("视觉文本搜图需填写 query")
    model = resolve_embedding_model_sync(db, kb.visual_embedding_model_config_id, kb.tenant_id)
    ensure_clip_model(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_texts(model, [text])[0]


async def embed_query_visual_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    query: str,
) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    text = (query or "").strip()
    if not text:
        raise BadRequestError("视觉文本搜图需填写 query")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    ensure_clip_model(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_texts(model, [text])[0]


async def embed_image_bytes_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    raw: bytes,
) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    ensure_clip_model(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]
