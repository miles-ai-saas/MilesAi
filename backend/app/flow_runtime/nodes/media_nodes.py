"""OcrExtract / AudioTranscribe 画布节点：从附件中提取文字。

OcrExtract — 读取图片附件 → OCR 文字提取 → 返回纯文本
AudioTranscribe — 读取音频附件 → Whisper 转写 → 返回纯文本

两者均通过 AttachmentService 鉴权读取对象存储中的附件字节，
再委托 rag.parse 模块进行实际解析。可在流程画布中作为 LLMCall 的前置节点。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.rag.parse.audio_parser import parse_audio
from app.rag.parse.image_parser import parse_image
from app.models.attachment import Attachment
from app.tenant.attachments.services.attachment import AttachmentService


async def ocr_extract(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """从图片附件中 OCR 提取文字。"""
    attachment_id = _resolve_attachment_id(node_data, inputs, "attachment_id")

    if not attachment_id:
        raise BadRequestError("OcrExtract 节点需要 attachment_id")

    async with AsyncSessionLocal() as db:
        tctx = _make_ctx(ctx)
        data, mime = await AttachmentService(db, tctx).read_image_bytes(
            UUID(attachment_id)
        )

    text = parse_image(data, f"ocr-{attachment_id}")

    return {
        "output": text,
        "attachment_id": str(attachment_id),
        "mime_type": mime,
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

    async with AsyncSessionLocal() as db:
        tctx = _make_ctx(ctx)
        att = await db.scalar(
            select(Attachment).where(Attachment.id == UUID(attachment_id))
        )
        if not att:
            raise BadRequestError(f"附件不存在: {attachment_id}")

        data, _ = await AttachmentService(db, tctx).read_image_bytes(
            UUID(attachment_id)
        )

    filename = att.filename or f"audio-{attachment_id}"
    text = parse_audio(data, filename)

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


def _make_ctx(ctx: RunContext):
    """构造带 attachment:read 权限的 TenantContext，供 AttachmentService 鉴权读取。"""
    return TenantContext(
        user_id=UUID(ctx.user_id) if ctx.user_id else None,
        tenant_id=UUID(ctx.tenant_id),
        username="flow_media",
        is_superuser=False,
        permissions=frozenset(["attachment:read"]),
    )
