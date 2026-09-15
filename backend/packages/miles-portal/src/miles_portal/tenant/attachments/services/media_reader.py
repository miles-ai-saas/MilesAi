"""媒体附件读取器（L1，实现 L3 中性 MediaReader 契约）。

两种实现互补：

- ``FlowMediaReader``：持有 tenant_id/user_id，每次读取开短会话并构造带
  ``attachment:read`` 权限的 TenantContext；装配点为 chat_rag.flow_run_context
  与 flows flow debug-run。
- ``SessionMediaReader``：复用调用方 ``db``/``ctx``，适用于已持有租户会话的
  请求/图节点场景（Agent 对话、RAG、工具循环）。

两者均委托 ``AttachmentService`` 完成租户鉴权 + 对象存储读取。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import AsyncSessionLocal
from miles_core.models.media.reader import AttachmentBytes
from miles_core.tenant import TenantContext
from miles_portal.tenant.attachments.services.attachment import AttachmentService


class FlowMediaReader:
    """短会话媒体读取器（每调用新开会话，与调用方事务无关）。"""

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
        """自开短会话读取图片字节；脏数据由 ``AttachmentService`` 兜底占位图。"""
        async with AsyncSessionLocal() as db:
            data, mime = await AttachmentService(db, self._ctx()).read_image_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime)

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        """自开短会话读取任意附件字节（不做图片类型校验）。"""
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


class SessionMediaReader:
    """会话绑定的媒体读取器（复用调用方 ``db``/``ctx``，不再开短会话）。

    适用于请求/图节点已持有租户会话的场景（Agent 对话、RAG、工具循环），
    与 ``FlowMediaReader``（每调用新开会话）互补。
    """

    def __init__(self, *, db: AsyncSession, ctx: TenantContext) -> None:
        self._db = db
        self._ctx = ctx

    async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        """复用调用方会话读取图片字节。"""
        data, mime = await AttachmentService(self._db, self._ctx).read_image_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime)

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        """复用调用方会话读取任意附件字节（不做图片类型校验）。"""
        data, mime, filename = await AttachmentService(self._db, self._ctx).read_attachment_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime, filename=filename)


def build_session_media_reader(db: AsyncSession, ctx: TenantContext) -> SessionMediaReader:
    """构造复用既有会话的 ``MediaReader``（装配点：chat_rag / RAG / 工具循环）。"""
    return SessionMediaReader(db=db, ctx=ctx)
