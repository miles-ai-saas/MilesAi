"""媒体/附件读取中立契约（L3 与 L1 实现共用）。

``AttachmentBytes``：读取结果的 L3 最小视图；``MediaReader`` 由 L1
``tenant.attachments.services.media_reader`` 实现，同时提供短会话读取器
（``FlowMediaReader``，租户鉴权 + 对象存储短会话）与复用调用方会话的读取器
（``SessionMediaReader``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

__all__ = ["AttachmentBytes", "MediaReader"]


@dataclass(frozen=True)
class AttachmentBytes:
    """附件字节读取结果：data / mime / filename（filename 供解析器推断格式）。"""

    data: bytes
    mime: str
    filename: str | None = None


class MediaReader(Protocol):
    """画布媒体节点所需的最小附件读取面（L1 注入）。"""

    async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        """按租户鉴权读取图片字节（非图片/未就绪抛业务异常）。"""
        ...

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        """按租户鉴权读取任意附件字节（不存在/未就绪抛业务异常）。"""
        ...
