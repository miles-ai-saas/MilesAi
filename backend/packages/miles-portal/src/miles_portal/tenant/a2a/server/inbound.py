"""A2A 入站 message 字段解析（纯逻辑；多模态见 inbound_parts）。"""

from __future__ import annotations

from miles_common.exceptions import BadRequestError
from miles_common.schemas.chat_io import CONVERSATION_ID_MAX_LENGTH


def extract_message_text(params: dict) -> str:
    """取 A2A ``message/send`` 的 ``params.message.parts`` 文本，多段以换行拼接。

    无任何非空文本段抛 ``BadRequestError``：静默返回空串会让本平台以空 query 空转一轮
    对话，且对端收到的是「谜之回答」而非参数错误。
    """
    message = params.get("message")
    if not isinstance(message, dict):
        raise BadRequestError("message/send 缺少 message 参数")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise BadRequestError("message/send 的 message.parts 必须是数组")

    texts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        raise BadRequestError("message/send 的 parts 中没有文本内容")
    return "\n".join(texts)


def extract_message_context_id(params: dict) -> str | None:
    """取 A2A ``message/send`` 的 ``message.contextId``（多轮上下文标识）。

    缺省或非字符串视为「无上下文」返回 ``None``：首轮调用本就不带，不能因此报错。
    超长则抛 ``BadRequestError`` —— 它作为 ``conversation_id`` 会被下游契约的
    ``max_length`` 拒绝并退化成 500，在入口判为参数错误更可诊断。
    """
    message = params.get("message")
    if not isinstance(message, dict):
        return None
    raw = message.get("contextId")
    if not isinstance(raw, str):
        return None
    context_id = raw.strip()
    if not context_id:
        return None
    if len(context_id) > CONVERSATION_ID_MAX_LENGTH:
        raise BadRequestError(f"message.contextId 过长（上限 {CONVERSATION_ID_MAX_LENGTH} 字符）")
    return context_id
