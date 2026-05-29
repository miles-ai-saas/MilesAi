"""多模态消息组装与附件解析单测。"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.schemas.media import MediaRefIn
from app.integrations.chat.multimodal import (
    build_user_message,
    messages_contain_image,
    resolve_media_refs,
)
from app.common.exceptions import BadRequestError


def test_build_user_message_text_only():
    msg = build_user_message(query="hello", media_parts=[])
    assert msg == {"role": "user", "content": "hello"}


def test_build_user_message_with_image_parts():
    parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]
    msg = build_user_message(query="看图", media_parts=parts)
    assert msg["role"] == "user"
    content = msg["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "看图"}
    assert content[1] == parts[0]


def test_build_user_message_image_only_default_text():
    parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]
    msg = build_user_message(query="", media_parts=parts)
    content = msg["content"]
    assert content[0]["text"] == "请根据附图回答。"


def test_messages_contain_image():
    assert not messages_contain_image([{"role": "user", "content": "hi"}])
    assert messages_contain_image(
        [
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": "data:..."}}],
            }
        ]
    )


@pytest.mark.asyncio
async def test_resolve_media_refs_too_many():
    ctx = MagicMock()
    ctx.tenant_id = uuid4()
    refs = [MediaRefIn(attachment_id=uuid4()) for _ in range(5)]
    with pytest.raises(BadRequestError, match="最多"):
        await resolve_media_refs(AsyncMock(), ctx, refs, max_count=4)


@pytest.mark.asyncio
async def test_resolve_media_refs_builds_data_url():
    tenant_id = uuid4()
    att_id = uuid4()
    ctx = MagicMock()
    ctx.tenant_id = tenant_id
    png = b"\x89PNG\r\n\x1a\n"
    with patch(
        "app.tenant.attachments.services.attachment.AttachmentService",
    ) as svc_cls:
        svc = MagicMock()
        svc.read_image_bytes = AsyncMock(return_value=(png, "image/png"))
        svc_cls.return_value = svc
        parts = await resolve_media_refs(
            AsyncMock(),
            ctx,
            [MediaRefIn(attachment_id=att_id)],
        )
    assert len(parts) == 1
    url = parts[0]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    decoded = base64.standard_b64decode(url.split(",", 1)[1])
    assert decoded == png


def test_chat_request_requires_query_or_media():
    from app.tenant.agents.schemas.agent import ChatMediaIn, ChatRequest

    with pytest.raises(ValueError, match="不能同时为空"):
        ChatRequest(query="", media=[])

    req = ChatRequest(query="", media=[ChatMediaIn(attachment_id=uuid4())])
    assert len(req.media) == 1
