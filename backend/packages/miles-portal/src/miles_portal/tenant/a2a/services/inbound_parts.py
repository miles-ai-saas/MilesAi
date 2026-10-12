"""A2A 入站 parts → 对话 ``query`` + ``media``（落库附件）。

纯解析在 ``tenant.a2a.inbound_parts``；本模块负责把 file bytes 写入附件表，
图片进 ``ChatRequest.media``，其它类型以说明文案拼进 query。
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from miles_common.schemas.chat_io import ChatMediaIn
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.inbound_parts import (
    compose_inbound_query,
    is_inbound_image,
    parse_inbound_parts,
)
from miles_portal.tenant.attachments.schemas.attachment import AttachmentUploadMeta
from miles_portal.tenant.attachments.services.attachment import AttachmentService

PURPOSE_A2A_INBOUND = "a2a_inbound"


@dataclass(frozen=True)
class InboundChatInput:
    """入站一轮对话的平台侧输入。"""

    query: str
    media: list[ChatMediaIn]


async def resolve_inbound_chat_input(
    db: AsyncSession,
    ctx: TenantContext,
    params: dict,
    *,
    agent_id: UUID,
) -> InboundChatInput:
    """解析 ``params.message.parts`` 并物化附件，供 ``message/send`` / ``message/stream`` 共用。"""
    parsed = parse_inbound_parts(params)
    media: list[ChatMediaIn] = []
    non_image_notes: list[str] = []
    attachment_svc = AttachmentService(db, ctx)
    meta = AttachmentUploadMeta(
        purpose=PURPOSE_A2A_INBOUND,
        resource_type="agent",
        resource_id=agent_id,
    )

    for item in parsed.files:
        upload = UploadFile(
            file=BytesIO(item.content),
            size=len(item.content),
            filename=item.filename,
            headers=Headers({"content-type": item.mime_type}),
        )
        att = await attachment_svc.upload(upload, meta)
        if is_inbound_image(item):
            media.append(ChatMediaIn(attachment_id=att.id))
        else:
            non_image_notes.append(
                f"[附件: {item.filename} ({item.mime_type}) attachment_id={att.id}]"
            )

    query = compose_inbound_query(parsed, non_image_notes=non_image_notes)
    # 仅图片、无文本时 query 可空：ChatRequest 允许 media 单独非空。
    return InboundChatInput(query=query, media=media)
