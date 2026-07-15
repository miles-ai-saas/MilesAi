"""生成类请求/结果 DTO。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ImageGenerateResult:
    """单次生图结果（可能多张）。"""

    attachment_ids: list[UUID]  # 产出附件 ID 列表
    mime_type: str  # 图片 MIME 类型
    width: int | None = None  # 宽度（像素，可选）
    height: int | None = None  # 高度（像素，可选）
    media_asset_ids: list[UUID] | None = None  # 对应生成素材 ID


@dataclass
class VideoGenerateResult:
    """生视频结果。"""

    attachment_id: UUID  # 产出视频附件 ID
    mime_type: str = "video/mp4"  # 视频 MIME 类型
    provider_task_id: str | None = None  # 供应商异步任务 ID（如有）
    duration_sec: int | None = None  # 视频时长（秒，可选）
    media_asset_id: UUID | None = None  # 生成素材 ID
