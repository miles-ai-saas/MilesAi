"""生成类参考图：鉴权读附件字节 → data URL（不向厂商暴露 OSS 签名 URL）。"""

from __future__ import annotations

import base64
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext


async def reference_image_data_url(
    db: AsyncSession,
    ctx: TenantContext,
    attachment_id: UUID,
) -> str:
    """读取租户图片附件并编码为 data URL，供万相/豆包图生图、图生视频使用。"""
    from app.tenant.attachments.services.attachment import AttachmentService

    data, mime = await AttachmentService(db, ctx).read_image_bytes(attachment_id)
    encoded = base64.standard_b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"
