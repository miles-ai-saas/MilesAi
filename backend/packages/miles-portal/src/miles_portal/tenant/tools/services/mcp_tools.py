"""绑定 MCP 服务的工具装配、元数据解析与执行分发（L1）。

职责
----
- ``load_mcp_tool_specs``：``agent.config.mcp_service_ids`` → 各服务 ``tools_cache``
  → L3 中性 ``McpToolSpec``，供 ``build_platform_tools`` 生成 function schema；
- ``resolve_mcp_tool_meta``：把 ``mcp__{service}__{tool}`` 反解为服务与原始 tool 名，
  产出与内置/自定义一致的工具元数据（``source=mcp``）；
- ``invoke_mcp_tool_by_slug``：按 slug 定位服务，把 LLM 参数还原为原始属性名后
  走 ``McpServiceManager.invoke_tool``（HTTP/SSE/STDIO 由既有链路处理）。

命名规则见 ``integrations.langchain.tools.compose_mcp_tool_name``。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.langchain.tools import (
    McpToolSpec,
    compose_mcp_tool_name,
    is_mcp_tool_name,
    mcp_param_alias,
)
from miles_common.exceptions import NotFoundError
from miles_core.soft_delete import not_deleted
from miles_core.tenant import TenantContext, tenant_filters
from miles_portal.tenant.mcp.models import McpService

_PLACEHOLDER_SUFFIX = "_placeholder"


def _bound_service_ids(agent_config: dict | None) -> list[UUID]:
    """解析 ``agent.config.mcp_service_ids`` 为 UUID 列表（容忍 str / 非法项）。"""
    cfg = agent_config if isinstance(agent_config, dict) else {}
    raw = cfg.get("mcp_service_ids") or []
    if isinstance(raw, str):
        raw = [raw]
    ids: list[UUID] = []
    for item in raw:
        try:
            ids.append(UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return ids


def _cached_tools(service: McpService) -> list[dict]:
    """过滤占位/无名条目后的 tools_cache。"""
    out: list[dict] = []
    for entry in service.tools_cache or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name.endswith(_PLACEHOLDER_SUFFIX):
            continue
        out.append(entry)
    return out


async def load_tenant_mcp_services(db: AsyncSession, ctx: TenantContext) -> list[McpService]:
    """加载本租户未删除的 MCP 服务（供解析与分发）。"""
    filters = [*tenant_filters(ctx, McpService.tenant_id), not_deleted(McpService)]
    rows = (await db.execute(select(McpService).where(*filters))).scalars().all()
    return list(rows)


async def load_mcp_tool_specs(
    db: AsyncSession,
    ctx: TenantContext,
    agent_config: dict | None,
) -> list[McpToolSpec]:
    """按 ``mcp_service_ids`` 装配绑定服务的 MCP 工具 spec（无绑定返回空）。"""
    service_ids = _bound_service_ids(agent_config)
    if not service_ids:
        return []
    filters = [
        *tenant_filters(ctx, McpService.tenant_id),
        not_deleted(McpService),
        McpService.id.in_(service_ids),
    ]
    rows = (await db.execute(select(McpService).where(*filters))).scalars().all()
    specs: list[McpToolSpec] = []
    for service in rows:
        for entry in _cached_tools(service):
            tool_name = str(entry.get("name"))
            schema = entry.get("inputSchema")
            specs.append(
                McpToolSpec(
                    slug=compose_mcp_tool_name(service.name, tool_name),
                    tool_name=tool_name,
                    service_id=str(service.id),
                    service_name=service.name,
                    description=entry.get("description") or None,
                    input_schema=schema if isinstance(schema, dict) else None,
                )
            )
    return specs


def find_mcp_tool(services: list[McpService], slug: str) -> tuple[McpService, dict] | None:
    """按 function name 反查 (service, tools_cache 条目)；无匹配返回 None。"""
    if not is_mcp_tool_name(slug):
        return None
    for service in services:
        for entry in _cached_tools(service):
            if compose_mcp_tool_name(service.name, str(entry.get("name"))) == slug:
                return service, entry
    return None


def mcp_tool_require_confirmation(entry: dict) -> bool:
    """MCP 工具确认策略：显式配置优先；``annotations.readOnlyHint`` 为真则免确认；否则默认需确认。"""
    explicit = entry.get("require_confirmation")
    if isinstance(explicit, bool):
        return explicit
    annotations = entry.get("annotations")
    if isinstance(annotations, dict) and annotations.get("readOnlyHint") is True:
        return False
    return True


def _tool_meta(slug: str, service: McpService, entry: dict) -> dict:
    tool_name = str(entry.get("name"))
    return {
        "slug": slug,
        "name": f"{service.name} · {tool_name}",
        "description": entry.get("description") or None,
        "require_confirmation": mcp_tool_require_confirmation(entry),
        "source": "mcp",
        "tool_id": None,
        "mcp_service_id": service.id,
        "mcp_tool_name": tool_name,
    }


async def resolve_mcp_tool_meta(db: AsyncSession, ctx: TenantContext, slug: str) -> dict | None:
    """解析 MCP function name 为工具元数据；非 MCP 名或无匹配返回 None。"""
    if not is_mcp_tool_name(slug):
        return None
    found = find_mcp_tool(await load_tenant_mcp_services(db, ctx), slug)
    if not found:
        return None
    service, entry = found
    return _tool_meta(slug, service, entry)


async def invoke_mcp_tool_by_slug(
    db: AsyncSession,
    ctx: TenantContext,
    slug: str,
    params: dict,
) -> dict:
    """按 function name 执行 MCP tools/call，返回规范化 output。

    参数名先按 ``inputSchema`` 还原为原始属性名（LLM 侧可能被清洗过），
    再交由 ``McpServiceManager`` 走既有 HTTP/SSE/STDIO + 审计链路。
    """
    found = find_mcp_tool(await load_tenant_mcp_services(db, ctx), slug)
    if not found:
        raise NotFoundError("MCP 工具不存在或服务未同步")
    service, entry = found
    alias = mcp_param_alias(entry.get("inputSchema"))
    wire_params = {alias.get(str(k), k): v for k, v in (params or {}).items()}

    # 延迟导入：避免 tools ↔ mcp.services 的模块级循环
    from miles_portal.tenant.mcp.schemas.mcp import McpToolInvokeRequest
    from miles_portal.tenant.mcp.services.mcp import McpServiceManager

    result = await McpServiceManager(db, ctx).invoke_tool(
        service.id,
        str(entry.get("name")),
        McpToolInvokeRequest(params=wire_params),
    )
    return result.output
