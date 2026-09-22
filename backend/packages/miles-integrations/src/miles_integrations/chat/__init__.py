"""对话多模态消息组装与附件解析。"""

from miles_integrations.chat.multimodal import (
    MAX_IMAGE_BYTES,
    MAX_MEDIA_PER_TURN,
    build_invoke_messages_with_media,
    build_user_message,
    media_refs_from_items,
    messages_contain_image,
    resolve_media_refs,
)

__all__ = [
    "MAX_IMAGE_BYTES",
    "MAX_MEDIA_PER_TURN",
    "build_invoke_messages_with_media",
    "build_user_message",
    "media_refs_from_items",
    "messages_contain_image",
    "resolve_media_refs",
]
