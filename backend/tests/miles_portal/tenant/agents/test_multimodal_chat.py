"""多模态消息组装与附件解析单测。"""

import base64
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn
from miles_integrations.chat.multimodal import (
    build_user_message,
    messages_contain_image,
    resolve_media_refs,
)


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
    refs = [MediaRefIn(attachment_id=uuid4()) for _ in range(11)]
    with pytest.raises(BadRequestError, match="最多"):
        await resolve_media_refs(MagicMock(), refs, max_count=10)


@pytest.mark.asyncio
async def test_resolve_media_refs_builds_data_url():
    from miles_core.models.media.reader import AttachmentBytes

    att_id = uuid4()
    png = b"\x89PNG\r\n\x1a\n"

    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            return AttachmentBytes(data=png, mime="image/png")

    parts = await resolve_media_refs(FakeReader(), [MediaRefIn(attachment_id=att_id)])
    assert len(parts) == 1
    url = parts[0]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    decoded = base64.standard_b64decode(url.split(",", 1)[1])
    assert decoded == png


@pytest.mark.asyncio
async def test_resolve_media_refs_rejects_oversize_image():
    from miles_core.models.media.reader import AttachmentBytes
    from miles_integrations.chat.multimodal import MAX_IMAGE_BYTES

    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            return AttachmentBytes(data=b"x" * (MAX_IMAGE_BYTES + 1), mime="image/png")

    with pytest.raises(BadRequestError, match="不能超过"):
        await resolve_media_refs(FakeReader(), [MediaRefIn(attachment_id=uuid4())])


def test_chat_request_requires_query_or_media():
    from miles_portal.tenant.agents.schemas.agent import ChatMediaIn, ChatRequest

    with pytest.raises(ValueError, match="不能同时为空"):
        ChatRequest(query="", media=[])

    req = ChatRequest(query="", media=[ChatMediaIn(attachment_id=uuid4())])
    assert len(req.media) == 1
