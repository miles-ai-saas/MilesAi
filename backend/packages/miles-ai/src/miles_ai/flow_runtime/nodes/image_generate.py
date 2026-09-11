"""
画布生图节点 ``ImageGenerate``。

默认异步：经 ``RunContext.submit_generative_image``（L1 注入）提交 ``generative_jobs`` + Celery；未注入（异步未启用）或 ``generative_image_async=False`` 时同步阻塞，同步分支经 ``RunContext.generate_image_sync``（L1 注入）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from miles_common.exceptions import BadRequestError
from miles_common.trace import get_trace_id
from miles_ai.flow_runtime.context_utils import tenant_context_from_run
from miles_ai.flow_runtime.types import RunContext
from miles_core.infra.db import AsyncSessionLocal
from miles_ai.integrations.generative.constants import PURPOSE_FLOW_GENERATED


def _optional_uuid(raw: Any) -> UUID | None:
    """将节点/入边中的 attachment id 转为 UUID，空值返回 None。"""
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

    image_att = _optional_uuid(inputs.get("image_attachment_id") or node_data.get("image_attachment_id"))
    n = int(node_data.get("n") or inputs.get("n") or 1)
    size = node_data.get("size") or inputs.get("size")

    submit = ctx.submit_generative_image
    if ctx.generative_image_async and submit is not None:
        async with AsyncSessionLocal() as db:
            tenant_ctx = tenant_context_from_run(ctx)
            job_id = await submit(
                db,
                tenant_ctx,
                prompt=prompt,
                size=str(size) if size else None,
                n=n,
                image_attachment_id=image_att,
                model_config_id=UUID(str(model_id)),
                agent_id=_optional_uuid(ctx.agent_id),
                agent_config=ctx.agent_config,
            )
            await db.commit()
        return {
            "kind": "image",
            "status": "pending",
            "generative_job_id": str(job_id),
            "message": "生图任务已提交，请通过 generative_job_id 查询进度",
        }

    resolver = ctx.resolve_generative_image
    if resolver is None:
        raise BadRequestError("生图模型解析器未装配（resolve_generative_image），无法同步生图")

    generate = ctx.generate_image_sync
    if generate is None:
        raise BadRequestError("生图编排未装配（generate_image_sync），无法同步生图")

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolver(
            db,
            tenant_ctx,
            model_config_id=UUID(str(model_id)),
            agent_config=ctx.agent_config,
        )
        result = await generate(
            db,
            tenant_ctx,
            model,
            prompt=prompt,
            size=size,
            n=n,
            reference_attachment_id=image_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=_optional_uuid(ctx.agent_id),
            trace_id=get_trace_id(),
        )
        await db.commit()
        primary = result.attachment_ids[0]
        return {
            "kind": "image",
            "attachment_id": str(primary),
            "attachment_ids": [str(i) for i in result.attachment_ids],
            "mime_type": result.mime_type,
        }
