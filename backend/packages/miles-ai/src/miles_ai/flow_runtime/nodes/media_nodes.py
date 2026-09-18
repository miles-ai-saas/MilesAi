"""OcrExtract / AudioTranscribe 画布节点：从附件中提取文字。

OcrExtract — 读取图片附件 → OCR 文字提取 → 返回纯文本
AudioTranscribe — 读取音频附件 → Whisper 转写 → 返回纯文本

媒体字节经 ``RunContext.media_reader``（L1 注入，实现见
``tenant.attachments.services.media_reader``）鉴权读取；OCR/音频解析仍委托
``rag.parse`` 模块 —— 该模块为同步 CPU / 子进程密集实现，故经
``asyncio.to_thread`` 离线，避免阻塞事件循环
（见 ``tests/test_no_blocking_calls_in_async.py``）。可在流程画布中作为 LLMCall 的前置节点。
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from miles_ai.flow_runtime.types import RunContext
from miles_ai.rag.parse.audio_parser import parse_audio
from miles_ai.rag.parse.image_parser import parse_image
from miles_common.exceptions import BadRequestError
from miles_core.models.media.reader import MediaReader


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

    text = await asyncio.to_thread(parse_image, att.data, f"ocr-{attachment_id}")

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
    text = await asyncio.to_thread(parse_audio, att.data, filename)

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
