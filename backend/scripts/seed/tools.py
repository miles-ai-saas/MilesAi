"""租户自定义工具种子（幂等，可重复执行）。

内置工具见 ``app.tenant.tools.builtin_registry``，本脚本仅写入 DB 自定义 HTTP/脚本示例。
命令：``python cli.py seed tools``
依赖：``seed tenant``、``seed categories``。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.soft_delete import not_deleted
from app.models.category import CategoryDomain
from app.tenant.tools.builtin_registry import BUILTIN_SLUGS
from app.tenant.tools.models import Tool, ToolType
from app.tenant.tools.parameters import normalize_parameters
from app.tenant.tools.script_validate import validate_script_source

from scripts.seed._helpers import category_id_by_slug, list_tenant_ids

SEED_CUSTOM_TOOLS: list[dict] = [
    {
        "slug": "http_echo",
        "name": "HTTP Echo（示例）",
        "description": "向 httpbin 发送 GET 请求并回显 query 参数，演示 HTTP 工具配置。",
        "tool_type": ToolType.HTTP,
        "category_slug": "integration",
        "parameters": [
            {
                "name": "message",
                "type": "string",
                "description": "写入 query 的 message 字段",
                "required": True,
            },
        ],
        "config": {
            "method": "GET",
            "url": "https://httpbin.org/get",
        },
    },
    {
        "slug": "json_placeholder_post",
        "name": "JSONPlaceholder 发帖（示例）",
        "description": "向 JSONPlaceholder 提交示例帖子，演示 POST JSON body。",
        "tool_type": ToolType.HTTP,
        "category_slug": "integration",
        "parameters": [
            {"name": "title", "type": "string", "description": "帖子标题", "required": True},
            {"name": "body", "type": "string", "description": "正文", "required": True},
            {
                "name": "userId",
                "type": "integer",
                "description": "用户 ID",
                "required": False,
                "default": 1,
            },
        ],
        "config": {
            "method": "POST",
            "url": "https://jsonplaceholder.typicode.com/posts",
            "body_mode": "json",
        },
    },
    {
        "slug": "github_repo_lookup",
        "name": "GitHub 仓库信息（示例）",
        "description": "查询公开 GitHub 仓库元数据（无需 Token，受 GitHub 速率限制）。",
        "tool_type": ToolType.HTTP,
        "category_slug": "data",
        "parameters": [
            {"name": "owner", "type": "string", "description": "组织或用户名", "required": True},
            {"name": "repo", "type": "string", "description": "仓库名", "required": True},
        ],
        "config": {
            "method": "GET",
            "url": "https://api.github.com/repos/{{owner}}/{{repo}}",
        },
    },
]

_SCRIPT_WORD_COUNT = """
def run(params):
    text = str(params.get("text") or "")
    words = [w for w in text.split() if w.strip()]
    return {"word_count": len(words), "char_count": len(text)}
""".strip()


async def _get_or_create_tool(
    session: AsyncSession,
    tenant_id,
    *,
    slug: str,
    name: str,
    description: str | None,
    tool_type: ToolType,
    category_id,
    parameters: list,
    config: dict,
) -> Tool:
    if slug in BUILTIN_SLUGS:
        raise ValueError(f"seed slug conflicts with builtin: {slug}")

    row = await session.scalar(
        select(Tool).where(
            Tool.tenant_id == tenant_id,
            Tool.slug == slug,
            not_deleted(Tool),
        )
    )
    if row:
        return row

    row = Tool(
        tenant_id=tenant_id,
        slug=slug,
        name=name.strip(),
        description=description,
        tool_type=tool_type,
        category_id=category_id,
        version="1.0.0",
        require_confirmation=False,
        parameters=normalize_parameters(parameters),
        config=config,
        is_active=True,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def seed_tools_for_tenant(session: AsyncSession, tenant_id) -> int:
    created = 0
    for spec in SEED_CUSTOM_TOOLS:
        before = await session.scalar(
            select(Tool.id).where(
                Tool.tenant_id == tenant_id,
                Tool.slug == spec["slug"],
                not_deleted(Tool),
            )
        )
        category_id = await category_id_by_slug(
            session, CategoryDomain.TOOL, spec.get("category_slug")
        )
        await _get_or_create_tool(
            session,
            tenant_id,
            slug=spec["slug"],
            name=spec["name"],
            description=spec.get("description"),
            tool_type=spec["tool_type"],
            category_id=category_id,
            parameters=spec.get("parameters") or [],
            config=spec.get("config") or {},
        )
        if before is None:
            created += 1

    if get_settings().mcp_runner_enabled:
        slug = "text_word_count"
        before = await session.scalar(
            select(Tool.id).where(
                Tool.tenant_id == tenant_id,
                Tool.slug == slug,
                not_deleted(Tool),
            )
        )
        category_id = await category_id_by_slug(session, CategoryDomain.TOOL, "general")
        await _get_or_create_tool(
            session,
            tenant_id,
            slug=slug,
            name="文本计数（脚本示例）",
            description="Python 脚本工具：统计词数与字符数（需 MCP Runner）。",
            tool_type=ToolType.SCRIPT,
            category_id=category_id,
            parameters=[
                {
                    "name": "text",
                    "type": "string",
                    "description": "待统计文本",
                    "required": True,
                },
            ],
            config={
                "language": "python",
                "source": validate_script_source(_SCRIPT_WORD_COUNT),
                "timeout_sec": 30,
                "max_memory_mb": 512,
            },
        )
        if before is None:
            created += 1

    await session.flush()
    return created


async def seed_tools(session: AsyncSession) -> None:
    total_created = 0
    for tenant_id in await list_tenant_ids(session):
        total_created += await seed_tools_for_tenant(session, tenant_id)
    print(f">>> tools seed: created {total_created} custom tool(s) across tenants")
