"""解析知识库绑定的 rerank ModelConfig（含 BYOK）。"""

from __future__ import annotations

from copy import copy
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.common.exceptions import BadRequestError
from app.core.soft_delete import not_deleted
from app.integrations.rerank.model_meta import ensure_rerank_model_type
from app.models.model import ModelConfig
from app.models.model_catalog import ModelPublishStatus
from app.models.model_tenant_credential import ModelTenantCredential
from app.tenant.models.services.model_resolve import load_tenant_credential


def _load_tenant_credential_sync(
    db: Session, tenant_id: UUID, model_config_id: UUID
) -> ModelTenantCredential | None:
    return db.execute(
        select(ModelTenantCredential).where(
            ModelTenantCredential.tenant_id == tenant_id,
            ModelTenantCredential.model_config_id == model_config_id,
            ModelTenantCredential.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _apply_builtin_credential(
    model: ModelConfig, cred: ModelTenantCredential | None
) -> ModelConfig:
    effective = copy(model)
    if cred:
        if cred.api_base:
            effective.api_base = cred.api_base
        if cred.api_key_encrypted:
            effective.api_key_encrypted = cred.api_key_encrypted
    if not effective.api_key_encrypted:
        raise BadRequestError(
            f"重排模型「{model.name}」未配置 API Key，请在模型供应商页配置密钥"
        )
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
    ensure_rerank_model_type(model)
    if not model.is_active:
        raise BadRequestError("重排模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置重排模型未发布或已下架")
        cred = await load_tenant_credential(db, tenant_id, model.id)
        return _apply_builtin_credential(model, cred)
    return _ensure_tenant_custom(model, tenant_id)


async def resolve_rerank_model_by_id(
    db: AsyncSession, model_id: UUID, tenant_id: UUID
) -> ModelConfig:
    model = (
        await db.execute(
            select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))
        )
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError("重排模型不存在")
    return await resolve_rerank_model(db, model, tenant_id)


def resolve_rerank_model_sync(
    db: Session, model_id: UUID, tenant_id: UUID
) -> ModelConfig:
    model = db.execute(
        select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))
    ).scalar_one_or_none()
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
