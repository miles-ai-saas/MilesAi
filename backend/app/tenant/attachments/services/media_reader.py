"""画布媒体节点附件读取器（L1，实现 L3 中性 MediaReader 契约）。

``FlowMediaReader`` 持有 tenant_id/user_id，每次读取开短会话并构造带
``attachment:read`` 权限的 TenantContext，委托 ``AttachmentService`` 完成租户
鉴权 + 对象存储读取；装配点为 chat_rag.flow_run_context 与 flows flow debug-run。
"""

from __future__ import annotations

from uuid import UUID

from app.core.tenant import TenantContext
from app.infra.db import AsyncSessionLocal
from app.models.media.reader import AttachmentBytes
from app.tenant.attachments.services.attachment import AttachmentService


class FlowMediaReader:
    """短会话媒体读取器（每调用新开 AsyncSessionLocal）。"""

    def __init__(self, *, tenant_id: UUID, user_id: UUID | None) -> None:
        self._tenant_id = tenant_id
        self._user_id = user_id

    def _ctx(self) -> TenantContext:
        return TenantContext(
            user_id=self._user_id,
            tenant_id=self._tenant_id,
            username="flow_media",
            is_superuser=False,
            permissions=frozenset(["attachment:read"]),
        )

    async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        async with AsyncSessionLocal() as db:
            data, mime = await AttachmentService(db, self._ctx()).read_image_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime)

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        async with AsyncSessionLocal() as db:
            data, mime, filename = await AttachmentService(db, self._ctx()).read_attachment_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime, filename=filename)


def build_flow_media_reader(
    *,
    tenant_id: str | UUID,
    user_id: str | UUID | None = None,
) -> FlowMediaReader:
    """构造 RunContext.media_reader（str/UUID 均可；None user_id 表示匿名运行）。"""
    return FlowMediaReader(
        tenant_id=UUID(str(tenant_id)),
        user_id=UUID(str(user_id)) if user_id else None,
    )
