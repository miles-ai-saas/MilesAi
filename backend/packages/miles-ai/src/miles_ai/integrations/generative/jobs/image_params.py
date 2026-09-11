"""从工具/节点参数构建异步生图任务 payload。"""

from __future__ import annotations

from uuid import UUID


def build_image_job_params(
    *,
    prompt: str,
    size: str | None = None,
    n: int = 1,
    image_attachment_id: UUID | None = None,
    model_config_id: UUID | None = None,
    agent_id: UUID | None = None,
    agent_config: dict | None = None,
) -> dict:
    """把生图工具/节点参数规范为异步任务 payload：UUID 序列化为字符串、prompt 去空白。"""
    return {
        "prompt": (prompt or "").strip(),
        "size": size,
        "n": n,
        "image_attachment_id": str(image_attachment_id) if image_attachment_id else None,
        "model_config_id": str(model_config_id) if model_config_id else None,
        "agent_id": str(agent_id) if agent_id else None,
        "agent_config": agent_config or {},
    }
