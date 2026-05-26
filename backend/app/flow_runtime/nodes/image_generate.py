"""
画布生图节点 ``ImageGenerate``。

默认异步：提交 ``generative_jobs`` + Celery；``RunContext.generative_image_async=False`` 时同步阻塞。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.flow_runtime.context_utils import tenant_context_from_run
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.generative import generate_image_for_model, resolve_image_gen_model
from app.integrations.generative.persist import PURPOSE_FLOW_GENERATED
from app.tenant.generative.schemas.job import ImageGenerativeJobCreate
from app.tenant.generative.services.job import GenerativeJobService


def _optional_uuid(raw: Any) -> UUID | None:
    if not raw:
        return None
    return UUID(str(raw))


async def image_generate(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """文生图 / 图生图：固定 prompt 优先；参考图来自入边或节点配置。"""
    fixed = str(node_data.get("prompt") or "").strip()
    if fixed:
        prompt = fixed
    else:
        upstream = inputs.get("prompt") or inputs.get("input")
        prompt = str(upstream or "").strip()
    if not prompt:
        raise BadRequestError("生图节点缺少 prompt")

    model_id = node_data.get("model_config_id")
    if not model_id:
        raise BadRequestError("生图节点未配置 image_gen 模型")

    image_att = _optional_uuid(
        inputs.get("image_attachment_id") or node_data.get("image_attachment_id")
    )
    n = int(node_data.get("n") or inputs.get("n") or 1)
    size = node_data.get("size") or inputs.get("size")

    if ctx.generative_image_async and GenerativeJobService.image_async_enabled():
        body = ImageGenerativeJobCreate(
            prompt=prompt,
            size=str(size) if size else None,
            n=n,
            image_attachment_id=image_att,
            model_config_id=UUID(str(model_id)),
        )
        async with AsyncSessionLocal() as db:
            tenant_ctx = tenant_context_from_run(ctx)
            out = await GenerativeJobService(db, tenant_ctx).submit_image(
                body,
                source="flow_node",
                agent_id=_optional_uuid(ctx.agent_id),
                agent_config=ctx.agent_config,
            )
            await db.commit()
        return {
            "kind": "image",
            "status": "pending",
            "generative_job_id": str(out.id),
            "message": "生图任务已提交，请通过 generative_job_id 查询进度",
        }

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolve_image_gen_model(
            db,
            tenant_ctx,
            model_config_id=UUID(str(model_id)),
            agent_config=ctx.agent_config,
        )
        result = await generate_image_for_model(
            db,
            tenant_ctx,
            model,
            prompt=prompt,
            size=size,
            n=n,
            reference_attachment_id=image_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=_optional_uuid(ctx.agent_id),
        )
        await db.commit()
        primary = result.attachment_ids[0]
        return {
            "kind": "image",
            "attachment_id": str(primary),
            "attachment_ids": [str(i) for i in result.attachment_ids],
            "mime_type": result.mime_type,
        }
