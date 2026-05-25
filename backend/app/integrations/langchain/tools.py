"""平台能力注册为 LangChain StructuredTool。

knowledge_search 工具：同步 DB + search_kb，供 Agent/流程调用单库检索。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.langchain.vectorstores import search_kb
from app.core.tenant import TenantContext


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


def _make_calculator_tool() -> StructuredTool:
    """安全数学表达式计算器。"""
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
    """出站 HTTP 请求（响应体截断 4KB）。"""
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


def make_knowledge_search_tool(ctx: TenantContext) -> StructuredTool:
    """绑定租户的单库语义检索工具。"""
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
        make_knowledge_search_tool(ctx),
    ]


async def invoke_platform_tool(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict[str, Any],
    *,
    tool_id: UUID | None = None,
) -> dict:
    """统一工具调用入口；内置名走 LangChain，其余走 tenant.tools.invoke。"""
    from app.tenant.tools.invoke import invoke_tool_by_name

    return await invoke_tool_by_name(db, ctx, name, params, tool_id=tool_id)
