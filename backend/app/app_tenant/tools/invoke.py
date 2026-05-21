"""内置与自定义工具执行。"""

import ast
import operator as op
import re
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_stack.langchain.vectorstores import search_kb
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext
from app.app_tenant.tools.models import Tool, ToolType
from app.core.soft_delete import is_marked_deleted


_SAFE_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}


def _eval_expr(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return _SAFE_OPS[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _SAFE_OPS[ast.USub](_eval_expr(node.operand))
    raise ValueError("不支持的表达式")


def safe_calculate(expression: str) -> float:
    tree = ast.parse(expression.strip(), mode="eval")
    return float(_eval_expr(tree.body))


async def invoke_builtin(
    name: str,
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
) -> dict:
    if name == "calculator":
        expr = params.get("expression") or params.get("expr") or params.get("query", "")
        if not expr:
            raise BadRequestError("calculator 需要 expression 参数")
        return {"result": safe_calculate(str(expr))}

    if name == "http_request":
        url = params.get("url")
        if not url:
            raise BadRequestError("http_request 需要 url 参数")
        method = str(params.get("method", "GET")).upper()
        async with httpx.AsyncClient(timeout=float(params.get("timeout", 10))) as client:
            resp = await client.request(method, url, json=params.get("json"), params=params.get("params"))
        text = resp.text[:4000]
        return {"status_code": resp.status_code, "body": text}

    if name == "knowledge_search":
        query = params.get("query") or params.get("q", "")
        kb_id = params.get("kb_id")
        if not query:
            raise BadRequestError("knowledge_search 需要 query 参数")
        if not kb_id:
            raise BadRequestError("knowledge_search 需要 kb_id 参数")
        hits = search_kb(
            str(query),
            tenant_id=ctx.tenant_id,
            kb_id=UUID(str(kb_id)),
            limit=int(params.get("limit", 5)),
        )
        return {"hits": hits}

    raise BadRequestError(f"未知内置工具: {name}")


async def invoke_custom_http(tool: Tool, params: dict) -> dict:
    cfg = tool.config or {}
    url = cfg.get("url") or params.get("url")
    if not url:
        raise BadRequestError("HTTP 工具未配置 url")
    method = str(cfg.get("method", params.get("method", "POST"))).upper()
    headers = cfg.get("headers") or {}
    async with httpx.AsyncClient(timeout=float(cfg.get("timeout", 15))) as client:
        resp = await client.request(method, url, json=params, headers=headers)
    return {
        "status_code": resp.status_code,
        "body": resp.text[:4000],
    }


async def invoke_tool_by_name(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    tool_id: UUID | None = None,
) -> dict:
    builtin_names = {"calculator", "http_request", "knowledge_search"}
    if name in builtin_names and not tool_id:
        return await invoke_builtin(name, params, db=db, ctx=ctx)

    if tool_id:
        tool = await db.get(Tool, tool_id)
    else:
        from sqlalchemy import select

        tool = await db.scalar(
            select(Tool).where(
                Tool.tenant_id == ctx.tenant_id,
                Tool.name == name,
                Tool.is_active.is_(True),
            )
        )
    if not tool or is_marked_deleted(tool):
        raise NotFoundError("工具不存在")
    if tool.tool_type == ToolType.HTTP:
        return await invoke_custom_http(tool, params)
    raise BadRequestError(f"暂不支持执行工具类型: {tool.tool_type}")
