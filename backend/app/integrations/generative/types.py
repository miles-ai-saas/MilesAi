"""生成类请求/结果 DTO。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ImageGenerateResult:
    """单次生图结果（可能多张）。"""

    attachment_ids: list[UUID]
    mime_type: str
    width: int | None = None
    height: int | None = None


@dataclass
class VideoGenerateResult:
    """生视频结果。"""

    attachment_id: UUID
    mime_type: str = "video/mp4"
    provider_task_id: str | None = None
    duration_sec: int | None = None
