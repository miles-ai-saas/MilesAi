"""视觉内容安全审核：使用 LLM Vision 模型检查图片/视频帧内容安全。

工作原理：
1. 读取图片/视频帧附件字节
2. 编码为 base64 data URL
3. 发送至租户已配置的 Vision/LLM 模型
4. 模型返回 JSON：{"safe": bool, "category": str, "reason": str}

审核维度：色情、暴力、血腥、恐怖主义、政治敏感、违法信息。
"""

from __future__ import annotations

import base64
import json
from uuid import UUID

from sqlalchemy import select

from miles_ai.integrations.langchain.chat_models import ainvoke_chat
from miles_core.logging import get_logger
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType
from miles_portal.tenant.attachments.services.attachment import AttachmentService
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink

logger = get_logger(__name__)

MODERATION_PROMPT = (
    "请审查以下图片内容是否包含违规信息。"
    "违规类型包括但不限于：色情、暴力、血腥、恐怖主义、政治敏感、违法信息。"
    '请用 JSON 格式回复：{"safe": true/false, "category": "违规类型或none", "reason": "简短说明"}'
)


async def check_media_safety(
    attachment_id: UUID,
    db,
    ctx,
) -> dict:
    """使用租户 Vision 模型审核图片内容安全。

    返回: safe, category, reason；无 Vision 模型或非图片时默认 safe=True。
    """
    data, mime = await AttachmentService(db, ctx).read_image_bytes(attachment_id)
    if not mime.startswith("image/"):
        return {"safe": True, "category": "none", "reason": "非图片附件"}

    image_b64 = base64.standard_b64encode(data).decode("ascii")
    image_url = f"data:{mime};base64,{image_b64}"

    # 优先 vision 模型，其次 llm（多数 llm 也支持 vision）
    model = await db.scalar(
        select(ModelConfig)
        .where(
            ModelConfig.model_type.in_([ModelCapabilityType.VISION.value, ModelCapabilityType.LLM.value]),
            ModelConfig.is_active.is_(True),
        )
        .limit(1)
    )
    if not model:
        return {"safe": True, "category": "none", "reason": "无可用模型"}

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
        usage_sink = ChatUsageSink(db=db, tenant_id=ctx.tenant_id, model=model)
        raw = await ainvoke_chat(
            model,
            messages,
            temperature=0.1,
            max_tokens=256,
            usage_sink=usage_sink,
        )
    except Exception as exc:
        logger.warning("视觉审核调用失败: %s", exc)
        return {"safe": True, "category": "error", "reason": str(exc)[:100]}

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            return {
                "safe": bool(parsed.get("safe", True)),
                "category": str(parsed.get("category", "")),
                "reason": str(parsed.get("reason", "")),
            }
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return {"safe": True, "category": "parse_error", "reason": raw[:200]}
