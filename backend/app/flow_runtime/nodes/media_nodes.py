"""OcrExtract / AudioTranscribe 画布节点：从附件中提取文字。

OcrExtract — 读取图片附件 → OCR 文字提取 → 返回纯文本
AudioTranscribe — 读取音频附件 → Whisper 转写 → 返回纯文本

媒体字节经 ``RunContext.media_reader``（L1 注入，实现见
``tenant.attachments.services.media_reader``）鉴权读取；OCR/音频解析仍委托
``rag.parse`` 模块。可在流程画布中作为 LLMCall 的前置节点。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext
from app.models.media.reader import MediaReader
from app.rag.parse.audio_parser import parse_audio
from app.rag.parse.image_parser import parse_image


async def ocr_extract(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """从图片附件中 OCR 提取文字。"""
    attachment_id = _resolve_attachment_id(node_data, inputs, "attachment_id")

    if not attachment_id:
        raise BadRequestError("OcrExtract 节点需要 attachment_id")

    reader = _require_media_reader(ctx)
    att = await reader.read_image_bytes(UUID(attachment_id))

    text = parse_image(att.data, f"ocr-{attachment_id}")

    return {
        "output": text,
        "attachment_id": str(attachment_id),
        "mime_type": att.mime,
    }


async def audio_transcribe(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """从音频附件中转写文字。"""
    attachment_id = _resolve_attachment_id(node_data, inputs, "attachment_id")

    if not attachment_id:
        raise BadRequestError("AudioTranscribe 节点需要 attachment_id")

    reader = _require_media_reader(ctx)
    att = await reader.read_attachment_bytes(UUID(attachment_id))

    filename = att.filename or f"audio-{attachment_id}"
    text = parse_audio(att.data, filename)

    return {
        "output": text,
        "attachment_id": str(attachment_id),
        "filename": filename,
    }


def _resolve_attachment_id(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    default_key: str = "attachment_id",
) -> str | None:
    """从 node_data.attachment_id、inputs[input_key] 或 inputs.media 列表解析附件 ID。"""
    raw = node_data.get("attachment_id")
    if raw:
        return str(raw)
    input_key = node_data.get("input_key") or default_key
    val = inputs.get(input_key)
    if val:
        return str(val)
    media = inputs.get("media") or []
    if isinstance(media, list) and media:
        for m in media:
            if isinstance(m, dict) and m.get("attachment_id"):
                return str(m["attachment_id"])
    return None


def _require_media_reader(ctx: RunContext) -> MediaReader:
    """取运行上下文注入的媒体读取器；未装配时报错。"""
    if ctx.media_reader is None:
        raise BadRequestError("运行上下文未提供媒体读取器")
    return ctx.media_reader
