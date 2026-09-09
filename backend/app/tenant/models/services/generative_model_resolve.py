"""生成类模型（image_gen / video_gen / tts）解析入口（L1）。

对话/工具/画布链路解析可用生成模型的唯一 L1 归口：显式 ``model_config_id``
（未指定时回落 ``agent_config`` 中 ``generative_*_model_id``，二者同分支）
> agent 绑定模型（若类型匹配）> 租户/平台默认
（``pick_default_generative_model``，vendor 优先），最后经
``resolve_model_for_invoke`` 合并 BYOK 凭证。

调用方：
- ``tenant.tools.builtins.generative``（工具 handler）
- ``tenant.generative.services.job_execution``（worker 编排，image/video）
- 画布生图/生视频节点：经 ``RunContext.resolve_generative_image/video`` 注入本模块函数引用
（见 ``flow_runtime/nodes/image_generate.py`` / ``video_generate.py``）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType, ModelVendor
from app.tenant.models.services.model_resolve import resolve_model_for_invoke

# 未显式指定 model_config_id 时的厂商优先顺序：万相(qwen) → 豆包 → 其它
_VENDOR_PRIORITY = case(
    (ModelConfig.vendor == ModelVendor.QWEN.value, 0),
    (ModelConfig.vendor == ModelVendor.DOUBAO.value, 1),
    else_=2,
)


async def pick_default_generative_model(
    db: AsyncSession,
    *,
    model_type: str,
    tenant_id: UUID,
) -> ModelConfig | None:
    """
    在租户级、平台级各取一条启用的生成模型，按 vendor 优先级返回首个命中。

    ``image_gen`` / ``video_gen`` 均优先 ``vendor=qwen``（通义万相）。
    """
    for tid in (tenant_id, None):
        stmt = (
            select(ModelConfig)
            .where(
                ModelConfig.is_active.is_(True),
                ModelConfig.model_type == model_type,
            )
            .order_by(_VENDOR_PRIORITY, ModelConfig.created_at.desc())
            .limit(1)
        )
        if tid is not None:
            stmt = stmt.where(ModelConfig.tenant_id == tid)
        else:
            stmt = stmt.where(ModelConfig.tenant_id.is_(None))
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row:
            return row
    return None


async def resolve_image_gen_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析生图用 ModelConfig（显式 id > agent 配置 > 智能体绑定模型若为 image_gen）。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_image_model_id"):
        raw_id = UUID(str(cfg["generative_image_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("生图模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.IMAGE_GEN.value:
            raise BadRequestError(f"模型「{row.name}」不是 image_gen 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.IMAGE_GEN.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.IMAGE_GEN.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 image_gen 模型，请配置通义万相或其它 image_gen 模型")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


async def resolve_video_gen_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析生视频模型：显式 id > ``generative_video_model_id`` > 租户/平台默认 video_gen。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_video_model_id"):
        raw_id = UUID(str(cfg["generative_video_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("生视频模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.VIDEO_GEN.value:
            raise BadRequestError(f"模型「{row.name}」不是 video_gen 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.VIDEO_GEN.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.VIDEO_GEN.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 video_gen 模型，请配置通义万相生视频模型")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


async def resolve_tts_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析 TTS 模型：显式 id > agent_model > 租户/平台默认 tts。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_tts_model_id"):
        raw_id = UUID(str(cfg["generative_tts_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("TTS 模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.TTS.value:
            raise BadRequestError(f"模型「{row.name}」不是 tts 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.TTS.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.TTS.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 tts 模型，请配置语音合成模型（如 DashScope CosyVoice）")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)
