"""
多模态媒体引用（智能体 ``ChatRequest.media``、流程 ``FlowRunRequest.media`` 共用）。

仅传 ``attachment_id``；识图时由 ``integrations.chat.multimodal`` 鉴权读字节并组装 data URL。
"""

from uuid import UUID

from pydantic import BaseModel, Field


class MediaRefIn(BaseModel):
    """运行时附图：仅 attachment_id，由服务端读对象存储转 data URL。"""

    attachment_id: UUID
    detail: str = Field(
        default="auto",
        description="OpenAI image detail: auto | low | high",
    )
