"""
解析知识库绑定的 rerank ModelConfig（含 BYOK）。

与 embedding 解析对称；rerank **无 local 免 Key** 例外（内置模型仍需租户或平台 Key）。

链路
----
``search_kb_chunks`` / ``search_multi_kb_async``
→ ``resolve_rerank_model_*`` → ``rag.retrieve.rerank.apply_rerank_to_hits``
→ ``integrations.rerank.registry``
"""

from __future__ import annotations

from copy import copy
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_ai.integrations.rerank.model_meta import ensure_rerank_model_type
from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus
from miles_core.models.model.tenant_credential import ModelTenantCredential
from miles_core.soft_delete import not_deleted
from miles_portal.tenant.models.services.model_resolve import load_tenant_credential


def _load_tenant_credential_sync(db: Session, tenant_id: UUID, model_config_id: UUID) -> ModelTenantCredential | None:
    return db.execute(
        select(ModelTenantCredential).where(
            ModelTenantCredential.tenant_id == tenant_id,
            ModelTenantCredential.model_config_id == model_config_id,
            ModelTenantCredential.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _apply_builtin_credential(model: ModelConfig, cred: ModelTenantCredential | None) -> ModelConfig:
    effective = copy(model)
    if cred:
        if cred.api_base:
            effective.api_base = cred.api_base
        if cred.api_key_encrypted:
            effective.api_key_encrypted = cred.api_key_encrypted
    if not effective.api_key_encrypted:
        raise BadRequestError(f"重排模型「{model.name}」未配置 API Key，请在模型供应商页配置密钥")
    return effective


def _ensure_tenant_custom(model: ModelConfig, tenant_id: UUID) -> ModelConfig:
    if model.tenant_id != tenant_id:
        raise BadRequestError("无权使用该重排模型")
    if not model.api_key_encrypted:
        raise BadRequestError(f"重排模型「{model.name}」未配置 API Key")
    return model


async def resolve_rerank_model(
    db: AsyncSession,
    model: ModelConfig,
    tenant_id: UUID,
) -> ModelConfig:
    """合并 BYOK 并校验内置/租户自定义 rerank 模型可用性。"""
    ensure_rerank_model_type(model)
    if not model.is_active:
        raise BadRequestError("重排模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置重排模型未发布或已下架")
        cred = await load_tenant_credential(db, tenant_id, model.id)
        return _apply_builtin_credential(model, cred)
    return _ensure_tenant_custom(model, tenant_id)


async def resolve_rerank_model_by_id(db: AsyncSession, model_id: UUID, tenant_id: UUID) -> ModelConfig:
    """按 ID 解析 KB 绑定的 rerank 模型（检索精排）。"""
    model = (await db.execute(select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig)))).scalar_one_or_none()
    if not model:
        raise BadRequestError("重排模型不存在")
    return await resolve_rerank_model(db, model, tenant_id)


def resolve_rerank_model_sync(db: Session, model_id: UUID, tenant_id: UUID) -> ModelConfig:
    """同步解析 rerank 模型（脚本或非 async 路径）。"""
    model = db.execute(select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))).scalar_one_or_none()
    if not model:
        raise BadRequestError("重排模型不存在")
    ensure_rerank_model_type(model)
    if not model.is_active:
        raise BadRequestError("重排模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置重排模型未发布或已下架")
        cred = _load_tenant_credential_sync(db, tenant_id, model.id)
        return _apply_builtin_credential(model, cred)
    return _ensure_tenant_custom(model, tenant_id)
