"""
多模态 user 消息：附件 → OpenAI content parts（base64 data URL）。

v1 不向厂商/浏览器提供对象存储签名 URL。
附件字节读取经注入的 ``MediaReader``（L3 中性契约 ``models.media.reader``；
L1 实现见 ``tenant.attachments.services.media_reader``），本模块不接触租户域。
"""

from __future__ import annotations

import base64
from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.models.media.reader import MediaReader

MAX_MEDIA_PER_TURN = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_DETAIL_VALUES = frozenset({"auto", "low", "high"})


def build_user_message(*, query: str, media_parts: list[dict[str, Any]]) -> dict[str, Any]:
    """组装 OpenAI 形状 user message（content 为 str 或 part 数组）。"""
    text = (query or "").strip()
    if not media_parts:
        return {"role": "user", "content": text}
    content: list[dict[str, Any]] = []
    content.append({"type": "text", "text": text or "请根据附图回答。"})
    content.extend(media_parts)
    return {"role": "user", "content": content}


def messages_contain_image(messages: list[dict[str, Any]]) -> bool:
    """任一 message 的 content 含 image_url part。"""
    for msg in messages:
        raw = msg.get("content")
        if not isinstance(raw, list):
            continue
        for part in raw:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


async def resolve_media_refs(
    reader: MediaReader,
    refs: list[MediaRefIn],
    *,
    max_count: int = MAX_MEDIA_PER_TURN,
) -> list[dict[str, Any]]:
    """批量解析为 LiteLLM/OpenAI image_url content parts（字节经 ``reader`` 读取）。"""
    if len(refs) > max_count:
        raise BadRequestError(f"每轮最多 {max_count} 张图片")
    parts: list[dict[str, Any]] = []
    for ref in refs:
        detail = (ref.detail or "auto").strip().lower()
        if detail not in _IMAGE_DETAIL_VALUES:
            raise BadRequestError(f"不支持的 image detail: {ref.detail}")
        url = await _resolve_attachment_data_url(reader, ref.attachment_id)
        image_url: dict[str, Any] = {"url": url}
        if detail != "auto":
            image_url["detail"] = detail
        parts.append({"type": "image_url", "image_url": image_url})
    return parts


async def build_invoke_messages_with_media(
    reader: MediaReader,
    *,
    prompt_text: str,
    media: list[MediaRefIn] | None,
    max_count: int = MAX_MEDIA_PER_TURN,
) -> list[dict[str, Any]]:
    """RAG / 兜底生成：单条 user message，可选附图（检索仍仅用文本 query）。"""
    if not media:
        return [{"role": "user", "content": prompt_text}]
    parts = await resolve_media_refs(reader, media, max_count=max_count)
    return [build_user_message(query=prompt_text, media_parts=parts)]


def media_refs_from_items(items: list[Any] | None) -> list[MediaRefIn]:
    """ChatRequest.media / state.media → MediaRefIn 列表。"""
    refs: list[MediaRefIn] = []
    for item in items or []:
        if isinstance(item, MediaRefIn):
            refs.append(item)
        elif isinstance(item, dict) and item.get("attachment_id"):
            refs.append(MediaRefIn.model_validate(item))
    return refs


async def _resolve_attachment_data_url(reader: MediaReader, attachment_id: UUID) -> str:
    """``reader`` 鉴权读图 → OpenAI/LiteLLM 所需的 data URL（不向厂商暴露 object_key）。"""
    att = await reader.read_image_bytes(attachment_id)
    if len(att.data) > MAX_IMAGE_BYTES:
        raise BadRequestError(f"单张图片不能超过 {MAX_IMAGE_BYTES // (1024 * 1024)}MB")
    encoded = base64.standard_b64encode(att.data).decode("ascii")
    return f"data:{att.mime};base64,{encoded}"
