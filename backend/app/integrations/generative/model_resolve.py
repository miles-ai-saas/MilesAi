"""生成类 ModelConfig 默认选取（多模态输出厂商优先级）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import ModelConfig
from app.models.model.catalog import ModelVendor

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
