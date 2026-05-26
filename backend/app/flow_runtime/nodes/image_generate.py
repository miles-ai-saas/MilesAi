"""
画布生图节点 ``ImageGenerate``。

``node_data``：``model_config_id``（必填）、可选固定 ``prompt`` / ``size`` / ``n``。
``inputs``：上游 ``prompt`` 或 ``input``（当节点未写固定 prompt 时）。
``output``：``{ kind, attachment_id, mime_type }``，下游可接 ``TextOutput`` 或展示链接。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.flow_runtime.context_utils import tenant_context_from_run
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.generative import generate_image_for_model, resolve_image_gen_model
from app.integrations.generative.persist import PURPOSE_FLOW_GENERATED


async def image_generate(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """文生图：固定 prompt 优先，否则取上游连线。"""
    # 属性面板「固定 prompt」非空时覆盖上游
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
            size=node_data.get("size") or inputs.get("size"),
            n=int(node_data.get("n") or 1),
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=UUID(ctx.agent_id) if ctx.agent_id else None,
        )
        primary = result.attachment_ids[0]
        return {
            "kind": "image",
            "attachment_id": str(primary),
            "mime_type": result.mime_type,
        }
