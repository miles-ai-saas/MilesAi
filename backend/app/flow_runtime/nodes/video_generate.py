"""
画布生视频节点 ``VideoGenerate``。

默认异步：提交 ``generative_jobs`` + Celery；``RunContext.generative_video_async=False`` 时同步轮询。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.common.trace import get_trace_id
from app.flow_runtime.context_utils import tenant_context_from_run
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.generative import generate_video_for_model, resolve_video_gen_model
from app.integrations.generative.persist import PURPOSE_FLOW_GENERATED
from app.tenant.generative.schemas.job import VideoGenerativeJobCreate
from app.tenant.generative.services.job import GenerativeJobService


def _optional_uuid(raw: Any) -> UUID | None:
    """将节点/入边中的 attachment id 转为 UUID，空值返回 None。"""
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

    first_att = _optional_uuid(inputs.get("image_attachment_id") or node_data.get("image_attachment_id"))
    last_att = _optional_uuid(inputs.get("last_frame_attachment_id") or node_data.get("last_frame_attachment_id"))
    duration = int(node_data.get("duration") or inputs.get("duration") or 5)
    resolution = node_data.get("resolution") or inputs.get("resolution")

    if ctx.generative_video_async and GenerativeJobService.video_async_enabled():
        body = VideoGenerativeJobCreate(
            prompt=prompt,
            duration=duration,
            resolution=str(resolution) if resolution else None,
            image_attachment_id=first_att,
            last_frame_attachment_id=last_att,
            model_config_id=UUID(str(model_id)),
        )
        async with AsyncSessionLocal() as db:
            tenant_ctx = tenant_context_from_run(ctx)
            out = await GenerativeJobService(db, tenant_ctx).submit_video(
                body,
                source="flow_node",
                agent_id=_optional_uuid(ctx.agent_id),
                agent_config=ctx.agent_config,
                trace_id=get_trace_id(),
            )
            await db.commit()
        return {
            "kind": "video",
            "status": "pending",
            "generative_job_id": str(out.id),
            "message": "生视频任务已提交，请通过 generative_job_id 查询进度",
        }

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
            duration=duration,
            resolution=resolution,
            image_attachment_id=first_att,
            last_frame_attachment_id=last_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=_optional_uuid(ctx.agent_id),
            trace_id=get_trace_id(),
        )
        await db.commit()
        return {
            "kind": "video",
            "attachment_id": str(result.attachment_id),
            "mime_type": result.mime_type,
            "duration_sec": result.duration_sec,
        }
