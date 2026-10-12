"""A2A ``tasks/pushNotificationConfig/{set,get,list,delete}`` 处理。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.tenant import TenantContext
from miles_core.url_security import validate_outbound_url
from miles_portal.tenant.a2a.server import (
    INVALID_PARAMS,
    TASK_NOT_FOUND,
    jsonrpc_error,
    jsonrpc_result,
)
from miles_portal.tenant.a2a.services.push_store import (
    delete_config,
    get_config,
    list_configs,
    set_config,
    to_task_push_config,
)
from miles_portal.tenant.a2a.services.server import load_owned_agent_task, parse_task_id


def _parse_task_id_for_push(params: dict) -> UUID:
    """``set`` 用 ``taskId``；其余方法与 ``tasks/*`` 一样用 ``id``。"""
    if isinstance(params.get("taskId"), str) and params["taskId"].strip():
        try:
            return UUID(params["taskId"].strip())
        except ValueError as exc:
            raise BadRequestError("params.taskId 不是合法的任务 ID") from exc
    return parse_task_id(params)


def _push_config_id(params: dict) -> str | None:
    raw = params.get("pushNotificationConfigId")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise BadRequestError("params.pushNotificationConfigId 无效")
    return raw.strip()


async def handle_push_notification_rpc(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    method: str,
    req_id: object,
    params: dict,
) -> dict:
    """分发四条 pushNotificationConfig 方法。"""
    try:
        task_id = _parse_task_id_for_push(params)
        await load_owned_agent_task(db, ctx, agent_id, task_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    if method.endswith("/set"):
        return await _set(ctx, task_id, req_id, params)
    if method.endswith("/get"):
        return await _get(ctx, task_id, req_id, params)
    if method.endswith("/list"):
        return await _list(ctx, task_id, req_id)
    if method.endswith("/delete"):
        return await _delete(ctx, task_id, req_id, params)
    return jsonrpc_error(req_id, INVALID_PARAMS, f"未知 push 方法: {method}")


async def _set(ctx: TenantContext, task_id: UUID, req_id: object, params: dict) -> dict:
    raw_cfg = params.get("pushNotificationConfig")
    if not isinstance(raw_cfg, dict):
        return jsonrpc_error(req_id, INVALID_PARAMS, "缺少 params.pushNotificationConfig")
    try:
        # 提前校验 URL，文案与 validate_outbound_url 一致
        validate_outbound_url(str(raw_cfg.get("url") or ""))
        cfg = await set_config(tenant_id=ctx.tenant_id, task_id=task_id, push_config=raw_cfg)
    except Exception as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    return jsonrpc_result(req_id, to_task_push_config(str(task_id), cfg))


async def _get(ctx: TenantContext, task_id: UUID, req_id: object, params: dict) -> dict:
    try:
        config_id = _push_config_id(params)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    cfg = await get_config(tenant_id=ctx.tenant_id, task_id=task_id, config_id=config_id)
    if cfg is None:
        if config_id:
            return jsonrpc_error(req_id, TASK_NOT_FOUND, "推送配置不存在")
        # 多条但未指定 id：参数不足
        listed = await list_configs(tenant_id=ctx.tenant_id, task_id=task_id)
        if not listed:
            return jsonrpc_error(req_id, TASK_NOT_FOUND, "推送配置不存在")
        return jsonrpc_error(req_id, INVALID_PARAMS, "存在多条推送配置，请提供 pushNotificationConfigId")
    return jsonrpc_result(req_id, to_task_push_config(str(task_id), cfg))


async def _list(ctx: TenantContext, task_id: UUID, req_id: object) -> dict:
    configs = await list_configs(tenant_id=ctx.tenant_id, task_id=task_id)
    return jsonrpc_result(
        req_id,
        [to_task_push_config(str(task_id), c) for c in configs],
    )


async def _delete(ctx: TenantContext, task_id: UUID, req_id: object, params: dict) -> dict:
    try:
        config_id = _push_config_id(params)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    if not config_id:
        return jsonrpc_error(req_id, INVALID_PARAMS, "缺少 params.pushNotificationConfigId")
    await delete_config(tenant_id=ctx.tenant_id, task_id=task_id, config_id=config_id)
    # 规范：delete 成功可回 null
    return jsonrpc_result(req_id, None)
