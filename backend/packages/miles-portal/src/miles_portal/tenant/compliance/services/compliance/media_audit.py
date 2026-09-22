"""视觉内容安全审核：使用 LLM Vision 模型检查图片/视频帧内容安全。

工作原理：
1. 读取图片/视频帧附件字节
2. 编码为 base64 data URL
3. 发送至租户已配置的 Vision/LLM 模型
4. 模型返回 JSON：{"safe": bool, "category": str, "reason": str}

审核维度：色情、暴力、血腥、恐怖主义、政治敏感、违法信息。

**当前状态：无调用方（未接线）** —— 自引入起全仓无任何 ``import``，故运行时不会执行；
合规相关文档中的对应条目已标注「未接线」。另注意两处能力边界，接入前需先解决：

- 只审核 ``image/*``；音/视频命中的是「非图片附件 ⇒ ``safe=True``」这条短路，
  即 PRD 所称「音视频内容安全检测」在本模块内并不成立；
- 无相关 OCR 合规逻辑。

接入前还须定：调用路径（对话带图 / 附件上传 / 画布）、warn 与 block 的取舍、
Vision 调用的成本与超时，以及「未审核」（``category`` 为 ``none``/``error``/
``parse_error``）与「审核通过」在调用侧的区分。
"""

from __future__ import annotations

import base64
import json
from uuid import UUID

from sqlalchemy import select

from miles_core.logging import get_logger
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType
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
        # 静默可接受：模型输出不保证是 JSON；解析失败以 parse_error 占位返回，调用侧可据此区分「未审核」。
        pass

    return {"safe": True, "category": "parse_error", "reason": raw[:200]}
