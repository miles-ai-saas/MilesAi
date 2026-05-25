"""
平台内置工具注册为 LangChain ``StructuredTool``。

与知识库相关
------------
- ``knowledge_search``：单 KB 同步检索（``integrations.langchain.vectorstores.search_kb``）
- 与 Agent ``_rag_chat`` 多 KB 路径独立；tool calling 模式下由 LLM 决定是否检索

其它内置：计算器、HTTP、日期时间等；租户自定义工具从 DB ``Tool`` 表加载。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.langchain.vectorstores import search_kb
from app.core.tenant import TenantContext, tenant_filters
from app.tenant.tools.models import Tool, ToolType
from app.tenant.tools.parameters import parameters_to_pydantic
from app.core.soft_delete import append_not_deleted


class CalculatorInput(BaseModel):
    expression: str = Field(..., description="数学表达式，如 1+2*3")


class HttpRequestInput(BaseModel):
    url: str
    method: str = "GET"
    timeout: float = 10.0


class KnowledgeSearchInput(BaseModel):
    query: str
    kb_id: str
    limit: int = 5


class DateTimeInput(BaseModel):
    timezone: str | None = Field(None, description="IANA 时区，默认 UTC")


def _make_calculator_tool() -> StructuredTool:
    def _run(expression: str) -> dict:
        from app.tenant.tools.invoke import safe_calculate

        return {"result": safe_calculate(expression)}

    return StructuredTool.from_function(
        func=_run,
        name="calculator",
        description="安全计算数学表达式",
        args_schema=CalculatorInput,
    )


def _make_http_request_tool() -> StructuredTool:
    import httpx

    def _run(url: str, method: str = "GET", timeout: float = 10.0) -> dict:
        resp = httpx.request(method.upper(), url, timeout=timeout)
        return {"status_code": resp.status_code, "body": resp.text[:4000]}

    return StructuredTool.from_function(
        func=_run,
        name="http_request",
        description="发起 HTTP 请求",
        args_schema=HttpRequestInput,
    )


def _make_datetime_tool() -> StructuredTool:
    def _run(timezone: str | None = None) -> dict:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tz_name = timezone or "UTC"
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        return {"datetime": now.isoformat(), "timezone": tz_name}

    return StructuredTool.from_function(
        func=_run,
        name="get_current_datetime",
        description="获取当前的日期时间",
        args_schema=DateTimeInput,
    )


def make_knowledge_search_tool(ctx: TenantContext) -> StructuredTool:
    """
    内置「知识库检索」工具（单库、同步会话）。

    走 ``search_kb`` → ``retriever.search_kb_chunks``，返回 hit 字典列表；
    不自动调用 LLM 生成答案（由 tool_agent 多轮对话决定后续）。
    """
    tenant_id = ctx.tenant_id

    def _run(query: str, kb_id: str, limit: int = 5) -> dict:
        from app.infra.db import get_sync_db
        from app.rag.load import load_kb_sync

        with get_sync_db() as db:
            kb = load_kb_sync(db, tenant_id, UUID(kb_id))
            hits = search_kb(query, kb=kb, db=db, limit=limit)
        return {"hits": hits}

    return StructuredTool.from_function(
        func=_run,
        name="knowledge_search",
        description="在指定知识库中语义检索",
        args_schema=KnowledgeSearchInput,
    )


def get_platform_tools(ctx: TenantContext) -> list[StructuredTool]:
    """返回当前租户可用的内置 StructuredTool 列表。"""
    return [
        _make_calculator_tool(),
        _make_http_request_tool(),
        _make_datetime_tool(),
        make_knowledge_search_tool(ctx),
    ]


def make_custom_http_tool(tool: Tool) -> StructuredTool:
    """将租户 HTTP 工具转为 StructuredTool。"""
    schema = parameters_to_pydantic(tool.parameters or [])
    description = tool.description or tool.name
    slug = tool.slug

    async def _arun(**kwargs: Any) -> dict:
        from app.tenant.tools.invoke import invoke_custom_http

        return await invoke_custom_http(tool, kwargs)

    return StructuredTool.from_function(
        coroutine=_arun,
        name=slug,
        description=description,
        args_schema=schema,
    )


async def load_tenant_http_tools(db: AsyncSession, ctx: TenantContext) -> list[StructuredTool]:
    """加载租户启用的自定义 HTTP 工具。"""
    filters = append_not_deleted(tenant_filters(ctx, Tool.tenant_id), Tool)
    rows = (
        await db.execute(
            select(Tool).where(*filters, Tool.is_active.is_(True), Tool.tool_type == ToolType.HTTP)
        )
    ).scalars().all()
    return [make_custom_http_tool(t) for t in rows]


async def get_all_platform_tools(db: AsyncSession, ctx: TenantContext) -> list[StructuredTool]:
    """内置 + 租户自定义 HTTP 工具。"""
    tools = get_platform_tools(ctx)
    tools.extend(await load_tenant_http_tools(db, ctx))
    return tools


async def invoke_platform_tool(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict[str, Any],
    *,
    tool_id: UUID | None = None,
    confirmed: bool = False,
    agent_id: UUID | None = None,
    invoke_source: str = "agent",
) -> dict:
    from app.tenant.tools.invoke import invoke_tool_with_context

    return await invoke_tool_with_context(
        db,
        ctx,
        name,
        params,
        tool_id=tool_id,
        confirmed=confirmed,
        actor_user_id=ctx.user_id,
        agent_id=agent_id,
        invoke_source=invoke_source,
    )
