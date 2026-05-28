"""从工具/节点参数构建异步生视频任务 payload。"""

from __future__ import annotations

from uuid import UUID


def build_video_job_params(
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    image_attachment_id: UUID | None = None,
    last_frame_attachment_id: UUID | None = None,
    model_config_id: UUID | None = None,
    agent_id: UUID | None = None,
    agent_config: dict | None = None,
) -> dict:
    return {
        "prompt": (prompt or "").strip(),
        "duration": duration,
        "resolution": resolution,
        "image_attachment_id": str(image_attachment_id) if image_attachment_id else None,
        "last_frame_attachment_id": (str(last_frame_attachment_id) if last_frame_attachment_id else None),
        "model_config_id": str(model_config_id) if model_config_id else None,
        "agent_id": str(agent_id) if agent_id else None,
        "agent_config": agent_config or {},
    }
