"""解析知识库绑定的向量化 ModelConfig（含本地模型免 Key）。"""

from __future__ import annotations

from copy import copy
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.ai_stack.embeddings.runtime import (
    INVOKE_MODE_LOCAL,
    ensure_embedding_model_type,
    invoke_mode_from_model,
)
from app.common.exceptions import BadRequestError
from app.core.soft_delete import not_deleted
from app.models.model import ModelConfig
from app.models.model_catalog import (
    BUILTIN_EMBEDDING_DEFAULT_CODE,
    ModelCapabilityType,
    ModelPublishStatus,
)
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


def _apply_builtin_credential(model: ModelConfig, cred: ModelTenantCredential | None) -> ModelConfig:
    effective = copy(model)
    if cred:
        if cred.api_base:
            effective.api_base = cred.api_base
        if cred.api_key_encrypted:
            effective.api_key_encrypted = cred.api_key_encrypted
    if invoke_mode_from_model(effective) == INVOKE_MODE_LOCAL:
        return effective
    if not effective.api_key_encrypted:
        raise BadRequestError(
            f"向量化模型「{model.name}」未配置 API Key，请在模型供应商页配置密钥"
        )
    return effective


def _ensure_tenant_custom(model: ModelConfig, tenant_id: UUID) -> ModelConfig:
    if model.tenant_id != tenant_id:
        raise BadRequestError("无权使用该向量化模型")
    if invoke_mode_from_model(model) != INVOKE_MODE_LOCAL and not model.api_key_encrypted:
        raise BadRequestError(f"向量化模型「{model.name}」未配置 API Key")
    return model


async def get_default_embedding_model(db: AsyncSession) -> ModelConfig:
    model = (
        await db.execute(
            select(ModelConfig).where(
                ModelConfig.tenant_id.is_(None),
                ModelConfig.model_code == BUILTIN_EMBEDDING_DEFAULT_CODE,
                ModelConfig.model_type == ModelCapabilityType.EMBEDDING.value,
                ModelConfig.is_active.is_(True),
                not_deleted(ModelConfig),
            )
        )
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError(
            "未找到默认向量化内置模型，请执行: python cli.py seed model-catalog"
        )
    return model


def get_default_embedding_model_sync(db: Session) -> ModelConfig:
    model = db.execute(
        select(ModelConfig).where(
            ModelConfig.tenant_id.is_(None),
            ModelConfig.model_code == BUILTIN_EMBEDDING_DEFAULT_CODE,
            ModelConfig.model_type == ModelCapabilityType.EMBEDDING.value,
            ModelConfig.is_active.is_(True),
            not_deleted(ModelConfig),
        )
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError(
            "未找到默认向量化内置模型，请执行: python cli.py seed model-catalog"
        )
    return model


async def resolve_embedding_model(
    db: AsyncSession,
    model: ModelConfig,
    tenant_id: UUID,
) -> ModelConfig:
    ensure_embedding_model_type(model)
    if not model.is_active:
        raise BadRequestError("向量化模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置向量化模型未发布或已下架")
        cred = await load_tenant_credential(db, tenant_id, model.id)
        return _apply_builtin_credential(model, cred)
    return _ensure_tenant_custom(model, tenant_id)


async def resolve_embedding_model_by_id(
    db: AsyncSession, model_id: UUID, tenant_id: UUID
) -> ModelConfig:
    model = (
        await db.execute(
            select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))
        )
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError("向量化模型不存在")
    return await resolve_embedding_model(db, model, tenant_id)


def resolve_embedding_model_sync(
    db: Session, model_id: UUID, tenant_id: UUID
) -> ModelConfig:
    model = db.execute(
        select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError("向量化模型不存在")
    ensure_embedding_model_type(model)
    if not model.is_active:
        raise BadRequestError("向量化模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置向量化模型未发布或已下架")
        cred = _load_tenant_credential_sync(db, tenant_id, model.id)
        return _apply_builtin_credential(model, cred)
    return _ensure_tenant_custom(model, tenant_id)
