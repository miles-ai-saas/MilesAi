"""视觉内容安全审核：使用 Vision/LLM 模型检查入站图片。

工作原理：
1. 校验附件为图片（非图片直接 ``safe=True`` 跳过）
2. 读取字节并编码为 base64 data URL
3. 发送至租户可见的 Vision（优先）或 LLM 模型
4. 模型返回 JSON：{"safe": bool, "category": str, "reason": str}

审核维度：色情、暴力、血腥、恐怖主义、政治敏感、违法信息。

调用方：``ComplianceInterceptMixin.check_media_input``（智能体对话 / 流程运行入站附图）。
音视频帧抽帧与 OCR 文本合规仍不在本模块（非图片短路为 safe）。
"""

from __future__ import annotations

import base64
import json
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.logging import get_logger
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType, ModelPublishStatus
from miles_core.soft_delete import not_deleted
from miles_core.tenant import TenantContext
from miles_integrations.langchain.chat_models import ainvoke_chat
from miles_portal.tenant.attachments.services.attachment import AttachmentService
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink

logger = get_logger(__name__)

MODERATION_PROMPT = (
    "请审查以下图片内容是否包含违规信息。"
    "违规类型包括但不限于：色情、暴力、血腥、恐怖主义、政治敏感、违法信息。"
    '请用 JSON 格式回复：{"safe": true/false, "category": "违规类型或none", "reason": "简短说明"}'
)

# 单次对话/流程最多审核的图片数（防 Vision 成本爆炸）
DEFAULT_MAX_MEDIA_AUDIT = 5


async def _pick_moderation_model(db: AsyncSession, tenant_id: UUID) -> ModelConfig | None:
    """优先 Vision，其次 LLM；限租户可见（本租户自定义 + 已发布内置）。"""
    visible = or_(
        ModelConfig.tenant_id == tenant_id,
        (ModelConfig.tenant_id.is_(None) & (ModelConfig.publish_status == ModelPublishStatus.PUBLISHED.value)),
    )
    for mtype in (ModelCapabilityType.VISION.value, ModelCapabilityType.LLM.value):
        model = (
            await db.execute(
                select(ModelConfig)
                .where(
                    ModelConfig.model_type == mtype,
                    ModelConfig.is_active.is_(True),
                    not_deleted(ModelConfig),
                    visible,
                )
                .order_by(ModelConfig.sort_order.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if model:
            return model
    return None


async def check_media_safety(
    attachment_id: UUID,
    db: AsyncSession,
    ctx: TenantContext,
) -> dict:
    """使用租户可见 Vision/LLM 审核单张图片。

    返回: ``safe`` / ``category`` / ``reason``。
    非图片、无模型、调用/解析失败均 fail-open（``safe=True``），由 ``category`` 区分原因。
    """
    att = await AttachmentService(db, ctx).get(attachment_id)
    mime = (att.mime_type or "").lower()
    if not mime.startswith("image/"):
        return {"safe": True, "category": "none", "reason": "非图片附件", "attachment_id": str(attachment_id)}

    try:
        data, mime = await AttachmentService(db, ctx).read_image_bytes(attachment_id)
    except Exception as exc:
        logger.warning("视觉审核读图失败 attachment_id=%s: %s", attachment_id, exc)
        return {
            "safe": True,
            "category": "error",
            "reason": f"读图失败:{str(exc)[:80]}",
            "attachment_id": str(attachment_id),
        }

    image_b64 = base64.standard_b64encode(data).decode("ascii")
    image_url = f"data:{mime};base64,{image_b64}"

    model = await _pick_moderation_model(db, ctx.tenant_id)
    if not model:
        return {"safe": True, "category": "none", "reason": "无可用模型", "attachment_id": str(attachment_id)}

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": MODERATION_PROMPT},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    try:
        model = await resolve_model_for_invoke(db, model, ctx.tenant_id)
        usage_sink = ChatUsageSink(tenant_id=ctx.tenant_id, model=model)
        raw = await ainvoke_chat(
            model,
            messages,
            temperature=0.1,
            max_tokens=256,
            usage_sink=usage_sink,
        )
    except Exception as exc:
        logger.warning("视觉审核调用失败: %s", exc, exc_info=True)
        return {
            "safe": True,
            "category": "error",
            "reason": str(exc)[:100],
            "attachment_id": str(attachment_id),
        }

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            return {
                "safe": bool(parsed.get("safe", True)),
                "category": str(parsed.get("category", "") or "none"),
                "reason": str(parsed.get("reason", "")),
                "attachment_id": str(attachment_id),
            }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        pass

    return {
        "safe": True,
        "category": "parse_error",
        "reason": (raw or "")[:200],
        "attachment_id": str(attachment_id),
    }
