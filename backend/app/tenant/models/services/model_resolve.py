"""
解析租户可用的有效 **对话/多模态** ModelConfig（平台 Key + BYOK）。

与 embedding/rerank 解析的分工
------------------------------
- 本模块：``ainvoke_chat``、LangGraph ``run_rag_workflow``、画布 ``llm_call``
- ``embedding_resolve`` / ``rerank_resolve``：知识库向量化与检索精排

``resolve_model_for_invoke`` 返回副本，合并 ``ModelTenantCredential`` 中的 api_key/api_base。
"""

from __future__ import annotations

from copy import copy
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.soft_delete import not_deleted
from app.models.model import ModelConfig
from app.models.model_catalog import ModelPublishStatus
from app.models.model_tenant_credential import ModelTenantCredential
from app.tenant.models.services.api_key_validation import assert_usable_api_key


async def load_tenant_credential(
    db: AsyncSession, tenant_id: UUID, model_config_id: UUID
) -> ModelTenantCredential | None:
    """加载租户对内置模型的 BYOK 凭证。"""
    row = (
        await db.execute(
            select(ModelTenantCredential).where(
                ModelTenantCredential.tenant_id == tenant_id,
                ModelTenantCredential.model_config_id == model_config_id,
                ModelTenantCredential.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    return row


def credential_status(model: ModelConfig, cred: ModelTenantCredential | None) -> str:
    """返回 platform / tenant / missing，供模型列表 UI 展示。"""
    from app.integrations.embeddings.constants import INVOKE_MODE_LOCAL
    from app.integrations.embeddings.model_meta import invoke_mode_from_model
    from app.models.model_catalog import ModelCapabilityType

    if model.model_type == ModelCapabilityType.EMBEDDING.value:
        if invoke_mode_from_model(model) == INVOKE_MODE_LOCAL:
            return "platform"
    if not model.is_builtin:
        return "tenant" if model.api_key_encrypted else "missing"
    if model.api_key_encrypted:
        return "platform"
    if cred and cred.api_key_encrypted:
        return "tenant"
    return "missing"


async def resolve_model_for_invoke(
    db: AsyncSession,
    model: ModelConfig,
    tenant_id: UUID,
) -> ModelConfig:
    """返回可用于 HTTP 调用的配置副本（合并租户 BYOK）。"""
    if not model.is_active:
        raise BadRequestError("模型已停用")
    if model.is_builtin:
        if model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("内置模型未发布或已下架")
        cred = await load_tenant_credential(db, tenant_id, model.id)
    else:
        if model.tenant_id != tenant_id:
            raise BadRequestError("无权使用该模型配置")
        cred = None

    effective = copy(model)
    if cred:
        if cred.api_base:
            effective.api_base = cred.api_base
        if cred.api_key_encrypted:
            effective.api_key_encrypted = cred.api_key_encrypted

    if not effective.api_key_encrypted:
        raise BadRequestError(
            f"模型「{model.name}」未配置 API Key，请在模型供应商页配置密钥"
        )
    assert_usable_api_key(
        effective.api_key_encrypted,
        model_name=model.name,
        vendor=model.vendor,
    )
    return effective


async def resolve_model_by_id(
    db: AsyncSession, model_id: UUID, tenant_id: UUID
) -> ModelConfig:
    model = (
        await db.execute(
            select(ModelConfig).where(ModelConfig.id == model_id, not_deleted(ModelConfig))
        )
    ).scalar_one_or_none()
    if not model:
        raise BadRequestError("模型配置不存在")
    return await resolve_model_for_invoke(db, model, tenant_id)
