"""画布平台工具节点（含技能包 skill_* 工具）。

调用链：``platform_tool`` → ``invoke_tool_with_context`` → ``handlers.BUILTIN_HANDLERS``。
节点 ``data.tool_slug`` 指定工具；``param_from_input`` / ``merge_input`` 合并上游 inputs。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.tenant.tools.invoke import invoke_tool_with_context


def _build_invoke_params(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """合并节点固定 params、param_from_input 映射与上游 inputs；按 slug 注入默认值。"""
    params = dict(node_data.get("params") or {})
    if not isinstance(params, dict):
        raise BadRequestError("params 须为对象")

    param_map = node_data.get("param_from_input") or {}
    if isinstance(param_map, dict):
        for param_name, input_key in param_map.items():
            if input_key in inputs:
                params[param_name] = inputs[input_key]

    if node_data.get("merge_input", True):
        for key, val in inputs.items():
            if key in ("input", "true", "false"):
                continue
            if key not in params and val is not None:
                params.setdefault(key, val)

    slug = str(node_data.get("tool_slug") or "").strip()
    if slug == "knowledge_search" and "kb_id" not in params and ctx.kb_ids:
        params.setdefault("kb_id", ctx.kb_ids[0])
    if slug == "skill_run_script" and "params" not in params and "hits" in inputs:
        params["params"] = {"hits": inputs["hits"]}
    return params


def _tenant_context_from_run(ctx: RunContext) -> "TenantContext":
    """从 RunContext 构造 TenantContext，供工具 invoke 鉴权。"""
    uid = UUID(ctx.user_id) if ctx.user_id else UUID(int=0)
    return TenantContext(
        user_id=uid,
        tenant_id=UUID(ctx.tenant_id),
        username="flow",
        is_superuser=ctx.is_superuser,
        permissions=ctx.permissions,
    )


async def platform_tool(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """执行内置或租户工具；绑定智能体时可用 skill_read_reference / skill_run_script。"""
    slug = str(node_data.get("tool_slug") or node_data.get("slug") or "").strip()
    if not slug:
        raise BadRequestError("平台工具节点须配置 tool_slug")

    params = _build_invoke_params(node_data, inputs, ctx)
    tenant_ctx = _tenant_context_from_run(ctx)
    agent_id = UUID(ctx.agent_id) if ctx.agent_id else None
    confirmed = bool(node_data.get("confirmed", True))

    async with AsyncSessionLocal() as db:
        output = await invoke_tool_with_context(
            db,
            tenant_ctx,
            slug,
            params,
            confirmed=confirmed,
            actor_user_id=tenant_ctx.user_id,
            agent_id=agent_id,
            invoke_source="flow",
        )
    return {"output": output, "tool_slug": slug}
