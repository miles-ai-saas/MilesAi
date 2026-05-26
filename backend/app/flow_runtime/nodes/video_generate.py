"""
画布生视频节点 ``VideoGenerate``（万相优先，节点内同步轮询至完成）。

``node_data``：``model_config_id``、``duration``、``resolution``、可选固定 ``prompt`` /
``image_attachment_id``（首帧）、``last_frame_attachment_id``（尾帧）。
``inputs``：同上键名，可由入边传入。
``output``：``{ kind: video, attachment_id, mime_type, duration_sec }``。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.flow_runtime.context_utils import tenant_context_from_run
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.generative import generate_video_for_model, resolve_video_gen_model
from app.integrations.generative.persist import PURPOSE_FLOW_GENERATED


def _optional_uuid(raw: Any) -> UUID | None:
    if not raw:
        return None
    return UUID(str(raw))


async def video_generate(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """文生视频 / 首帧图生视频 / 首尾帧生视频。"""
    fixed = str(node_data.get("prompt") or "").strip()
    if fixed:
        prompt = fixed
    else:
        upstream = inputs.get("prompt") or inputs.get("input")
        prompt = str(upstream or "").strip()
    if not prompt:
        raise BadRequestError("生视频节点缺少 prompt")

    model_id = node_data.get("model_config_id")
    if not model_id:
        raise BadRequestError("生视频节点未配置 video_gen 模型")

    first_att = _optional_uuid(
        inputs.get("image_attachment_id") or node_data.get("image_attachment_id")
    )
    last_att = _optional_uuid(
        inputs.get("last_frame_attachment_id") or node_data.get("last_frame_attachment_id")
    )

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolve_video_gen_model(
            db,
            tenant_ctx,
            model_config_id=UUID(str(model_id)),
            agent_config=ctx.agent_config,
        )
        result = await generate_video_for_model(
            db,
            tenant_ctx,
            model,
            prompt=prompt,
            duration=int(node_data.get("duration") or inputs.get("duration") or 5),
            resolution=node_data.get("resolution") or inputs.get("resolution"),
            image_attachment_id=first_att,
            last_frame_attachment_id=last_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=UUID(ctx.agent_id) if ctx.agent_id else None,
        )
        return {
            "kind": "video",
            "attachment_id": str(result.attachment_id),
            "mime_type": result.mime_type,
            "duration_sec": result.duration_sec,
        }
