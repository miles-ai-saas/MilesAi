"""
平台内置工具注册为 LangChain ``StructuredTool``。

调用链
------
``run_tool_calling_chat`` → ``get_all_platform_tools`` → 本模块 ``StructuredTool`` 列表
→ LLM 选工具 → ``invoke_tool_with_context``（实际执行在 ``tenant.tools.builtins``）。

与知识库相关
------------
- ``knowledge_search``：单 KB 同步检索（``integrations.langchain.vectorstores.search_kb``）
- 与 Agent ``_rag_chat`` 多 KB 路径独立；tool calling 模式下由 LLM 决定是否检索

生成类 / 技能类
---------------
``generate_*``、``skill_*`` 的 ``_arun`` 仅占位（抛错提示走 invoke）；
schema 供 LLM 填参，执行统一经 ``invoke_tool_with_context`` 与确认策略。

其它内置：计算器、HTTP、日期时间等；租户自定义工具从 DB ``Tool`` 表加载。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import append_not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.infra.db import get_sync_db
from app.integrations.langchain.vectorstores import search_kb
from app.rag.load import load_kb_sync
from app.tenant.tools.invoke import (
    invoke_custom_http,
    invoke_tool_with_context,
    safe_calculate,
)
from app.tenant.tools.models import Tool, ToolType
from app.tenant.tools.parameters import parameters_to_pydantic


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


# --- 生成类工具 schema（实际执行在 tenant.tools.invoke，需 enable_generative_tools）---


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., description="画面描述")
    size: str | None = Field(None, description="如 1024x1024；≥1280 边长或多张需用户确认")
    image_attachment_id: str | None = Field(None, description="参考图 attachment_id（图生图）")
    n: int | None = Field(None, description="生成张数 1–4；≥3 需用户确认")
    model_config_id: str | None = Field(None, description="image_gen 模型配置 UUID")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., description="视频描述")
    duration: int | None = Field(None, description="时长秒数，默认 5")
    resolution: str | None = Field(None, description="720P 或 1080P")
    image_attachment_id: str | None = Field(None, description="首帧图 attachment_id")
    last_frame_attachment_id: str | None = Field(
        None,
        description="尾帧图 attachment_id（首尾帧生视频，须与首帧同传）",
    )
    model_config_id: str | None = Field(None, description="video_gen 模型配置 UUID")


class DateTimeInput(BaseModel):
    timezone: str | None = Field(None, description="IANA 时区，默认 UTC")


class SkillReadReferenceInput(BaseModel):
    path: str = Field(..., description="相对技能根的路径，如 references/guide.md")
    max_chars: int | None = Field(None, description="最大读取字符数，默认 12000")


class SkillRunScriptInput(BaseModel):
    path: str = Field(..., description="scripts/ 下脚本路径，如 scripts/example.py")
    params: dict = Field(default_factory=dict, description="传入 run(params) 的参数字典")
    timeout_sec: int | None = Field(None, description="超时秒数，默认 30")
    max_memory_mb: int | None = Field(None, description="内存上限 MB，默认 512")


def _make_calculator_tool() -> StructuredTool:
    """内置 calculator；同步 ``safe_calculate``。"""
    def _run(expression: str) -> dict:
        return {"result": safe_calculate(expression)}

    return StructuredTool.from_function(
        func=_run,
        name="calculator",
        description="安全计算数学表达式",
        args_schema=CalculatorInput,
    )


def _make_http_request_tool() -> StructuredTool:
    """内置 http_request；直连 httpx（tool_agent 路径不经 outbound URL 校验）。"""
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
    """内置 get_current_datetime；IANA 时区，默认 UTC。"""
    def _run(timezone: str | None = None) -> dict:
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


def _make_skill_read_reference_tool() -> StructuredTool:
    """技能包 references/ 读取；执行走 invoke，此处仅暴露 schema。"""
    async def _arun(path: str, max_chars: int | None = None) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行技能工具")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="skill_read_reference",
        description="读取绑定技能包 references/ 或 assets/ 下的文本文件",
        args_schema=SkillReadReferenceInput,
    )


def _make_skill_run_script_tool() -> StructuredTool:
    """技能包 scripts/ 沙箱执行；执行走 invoke，此处仅暴露 schema。"""
    async def _arun(
        path: str,
        params: dict | None = None,
        timeout_sec: int | None = None,
        max_memory_mb: int | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行技能工具")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="skill_run_script",
        description="在沙箱中执行绑定技能包 scripts/ 下的 Python 脚本",
        args_schema=SkillRunScriptInput,
    )


def get_skill_bound_tools() -> list[StructuredTool]:
    """Agent 绑定 ``skill_package_id`` 时追加的技能工具对。"""
    return [_make_skill_read_reference_tool(), _make_skill_run_script_tool()]


def _make_generate_image_tool() -> StructuredTool:
    """generate_image schema；``enable_generative_tools`` 时挂载。"""
    async def _arun(
        prompt: str,
        size: str | None = None,
        image_attachment_id: str | None = None,
        n: int | None = None,
        model_config_id: str | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 generate_image")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="generate_image",
        description="根据文字描述生成图片，结果保存为附件",
        args_schema=GenerateImageInput,
    )


def _make_generate_video_tool() -> StructuredTool:
    """generate_video schema；异步 Celery 任务，常需用户确认。"""
    async def _arun(
        prompt: str,
        duration: int | None = None,
        resolution: str | None = None,
        image_attachment_id: str | None = None,
        last_frame_attachment_id: str | None = None,
        model_config_id: str | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 generate_video")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="generate_video",
        description="根据文字描述生成短视频（万相/豆包 Seedance；耗时长，需用户确认）",
        args_schema=GenerateVideoInput,
    )


def get_generative_tools() -> list[StructuredTool]:
    """由 ``get_all_platform_tools`` 在 ``agent.config.enable_generative_tools`` 时挂载。"""
    return [_make_generate_image_tool(), _make_generate_video_tool()]


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
        return await invoke_custom_http(tool, kwargs)

    return StructuredTool.from_function(
        coroutine=_arun,
        name=slug,
        description=description,
        args_schema=schema,
    )


def make_custom_script_tool(tool: Tool) -> StructuredTool:
    """将租户 Python 脚本工具转为 StructuredTool（schema 供 LLM；执行走 invoke）。"""
    schema = parameters_to_pydantic(tool.parameters or [])
    description = tool.description or tool.name
    slug = tool.slug

    async def _arun(**kwargs: Any) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行脚本工具")

    return StructuredTool.from_function(
        coroutine=_arun,
        name=slug,
        description=description,
        args_schema=schema,
    )


async def load_tenant_custom_tools(db: AsyncSession, ctx: TenantContext) -> list[StructuredTool]:
    """加载租户启用的自定义 HTTP / 脚本工具。"""
    filters = append_not_deleted(tenant_filters(ctx, Tool.tenant_id), Tool)
    rows = (
        await db.execute(
            select(Tool).where(
                *filters,
                Tool.is_active.is_(True),
                Tool.tool_type.in_([ToolType.HTTP, ToolType.SCRIPT]),
            )
        )
    ).scalars().all()
    out: list[StructuredTool] = []
    for t in rows:
        if t.tool_type == ToolType.HTTP:
            out.append(make_custom_http_tool(t))
        elif t.tool_type == ToolType.SCRIPT:
            out.append(make_custom_script_tool(t))
    return out


async def get_all_platform_tools(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    agent_config: dict | None = None,
) -> list[StructuredTool]:
    """内置 + 租户自定义 HTTP / 脚本工具；绑定技能包时追加 skill_* 工具。"""
    tools = get_platform_tools(ctx)
    cfg = agent_config if isinstance(agent_config, dict) else {}
    if cfg.get("skill_package_id"):
        tools = [*tools, *get_skill_bound_tools()]
    if cfg.get("enable_generative_tools"):
        # 与 RAG 可共存：仍走 tool_agent，由 LLM 决定是否调用 generate_*
        tools = [*tools, *get_generative_tools()]
    tools.extend(await load_tenant_custom_tools(db, ctx))
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
    """LangChain/流程侧统一入口：委托 ``invoke_tool_with_context``（含确认与审计）。"""
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
