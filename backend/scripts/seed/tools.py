"""租户自定义工具种子（幂等，可重复执行）。

内置工具见 ``app.tenant.tools.builtin_registry``。本脚本写入少量**可直连第三方 API** 的 HTTP 工具模板；
创建后请在工具详情中填写 ``headers`` / 参数中的 API Key（见各工具描述）。

命令：``python cli.py seed tools``
依赖：``seed tenant``、``seed categories``。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import mark_deleted, not_deleted
from app.models.category import CategoryDomain
from app.tenant.tools.builtin_registry import BUILTIN_SLUGS
from app.tenant.tools.models import Tool, ToolType
from app.tenant.tools.parameters import normalize_parameters

from scripts.seed._helpers import category_id_by_slug, list_tenant_ids

SEED_VERSION = 2

# 旧版演示工具（httpbin / GitHub 等），重复 seed 时软删
OBSOLETE_SEED_SLUGS = frozenset(
    {
        "http_echo",
        "json_placeholder_post",
        "github_repo_lookup",
        "text_word_count",
        "aigc_text_moderation",
    }
)

# 精而不多：网页阅读 / 联网搜索 / 无头浏览器（AIGC 检测暂不种子）
SEED_CUSTOM_TOOLS: list[dict] = [
    {
        "slug": "jina_reader",
        "name": "Jina Reader · 网页转文本",
        "description": (
            "将任意 URL 转为 LLM 友好的 Markdown/纯文本（r.jina.ai）。"
            "免费档可不填 API Key；生产建议在工具配置 headers 增加 "
            "Authorization: Bearer <JINA_API_KEY> 以提高限额。"
        ),
        "tool_type": ToolType.HTTP,
        "category_slug": "data",
        "parameters": [
            {
                "name": "url",
                "type": "string",
                "description": "完整网页 URL，须含 https://",
                "required": True,
            },
            {
                "name": "jina_api_key",
                "type": "string",
                "description": "可选；若填写则通过 Authorization 头发送",
                "required": False,
            },
        ],
        "config": {
            "method": "GET",
            "url": "https://r.jina.ai/{{url}}",
            "send_query_params": False,
            "headers": {
                "Accept": "text/plain",
                "Authorization": "Bearer {{jina_api_key}}",
            },
            "timeout_sec": 90,
        },
    },
    {
        "slug": "jina_search",
        "name": "Jina Search · 联网搜索",
        "description": (
            "通过 s.jina.ai 检索 Web 并返回 Top 结果的正文摘要（适合 RAG / Agent 补全事实）。"
            "可选 jina_api_key 提高速率限制。"
        ),
        "tool_type": ToolType.HTTP,
        "category_slug": "data",
        "parameters": [
            {
                "name": "q",
                "type": "string",
                "description": "搜索关键词或自然语言问题",
                "required": True,
            },
            {
                "name": "jina_api_key",
                "type": "string",
                "description": "可选 Jina API Key",
                "required": False,
            },
        ],
        "config": {
            "method": "GET",
            "url": "https://s.jina.ai/{{q}}",
            "send_query_params": False,
            "headers": {
                "Accept": "text/plain",
                "Authorization": "Bearer {{jina_api_key}}",
            },
            "timeout_sec": 90,
        },
    },
    {
        "slug": "browserless_screenshot",
        "name": "Browserless · 网页截图",
        "description": (
            "调用 Browserless /screenshot 对 URL 截图（返回 JSON，含 base64 或 CDN 链接字段，视账户配置而定）。"
            "须在参数 browserless_token 填入控制台 Token；按量计费，默认需用户确认后执行。"
        ),
        "tool_type": ToolType.HTTP,
        "category_slug": "integration",
        "require_confirmation": True,
        "parameters": [
            {
                "name": "url",
                "type": "string",
                "description": "要截图的页面 URL",
                "required": True,
            },
            {
                "name": "browserless_token",
                "type": "string",
                "description": "Browserless API Token",
                "required": True,
            },
        ],
        "config": {
            "method": "POST",
            "url": "https://production-sfo.browserless.io/screenshot?token={{browserless_token}}",
            "body_mode": "json",
            "body_exclude": ["browserless_token"],
            "timeout_sec": 120,
        },
    },
    {
        "slug": "browserless_pdf",
        "name": "Browserless · 网页转 PDF",
        "description": (
            "调用 Browserless /pdf 将 URL 渲染为 PDF（响应为 application/pdf 二进制，试调用结果截断展示）。"
            "须填写 browserless_token；适合报告归档、投放落地页导出。"
        ),
        "tool_type": ToolType.HTTP,
        "category_slug": "integration",
        "require_confirmation": True,
        "parameters": [
            {
                "name": "url",
                "type": "string",
                "description": "要导出的页面 URL",
                "required": True,
            },
            {
                "name": "browserless_token",
                "type": "string",
                "description": "Browserless API Token",
                "required": True,
            },
        ],
        "config": {
            "method": "POST",
            "url": "https://production-sfo.browserless.io/pdf?token={{browserless_token}}",
            "body_mode": "json",
            "body_exclude": ["browserless_token"],
            "timeout_sec": 120,
        },
    },
]

CURRENT_SEED_SLUGS = {t["slug"] for t in SEED_CUSTOM_TOOLS}


def _seed_config(cfg: dict) -> dict:
    out = dict(cfg)
    out["seed"] = True
    out["seed_version"] = SEED_VERSION
    return out


async def _upsert_seed_tool(
    session: AsyncSession,
    tenant_id,
    *,
    spec: dict,
) -> tuple[Tool, bool]:
    """返回 (row, created)。已软删的同 slug 记录会恢复并更新。"""
    slug = spec["slug"]
    if slug in BUILTIN_SLUGS:
        raise ValueError(f"seed slug conflicts with builtin: {slug}")

    row = await session.scalar(
        select(Tool).where(
            Tool.tenant_id == tenant_id,
            Tool.slug == slug,
        )
    )
    category_id = await category_id_by_slug(
        session, CategoryDomain.TOOL, spec.get("category_slug")
    )
    parameters = normalize_parameters(spec.get("parameters") or [])
    config = _seed_config(spec.get("config") or {})
    created = row is None

    if row:
        row.deleted_at = None
        row.name = spec["name"].strip()
        row.description = spec.get("description")
        row.tool_type = spec["tool_type"]
        row.category_id = category_id
        row.parameters = parameters
        row.config = config
        row.require_confirmation = bool(spec.get("require_confirmation", False))
        row.is_active = True
        row.version = "1.0.0"
    else:
        row = Tool(
            tenant_id=tenant_id,
            slug=slug,
            name=spec["name"].strip(),
            description=spec.get("description"),
            tool_type=spec["tool_type"],
            category_id=category_id,
            version="1.0.0",
            require_confirmation=bool(spec.get("require_confirmation", False)),
            parameters=parameters,
            config=config,
            is_active=True,
        )
        session.add(row)

    await session.flush()
    await session.refresh(row)
    return row, created


async def _retire_obsolete_seeds(session: AsyncSession, tenant_id) -> int:
    retired = 0
    rows = await session.scalars(
        select(Tool).where(
            Tool.tenant_id == tenant_id,
            not_deleted(Tool),
        )
    )
    for row in rows:
        cfg = row.config or {}
        slug = row.slug
        if slug in OBSOLETE_SEED_SLUGS:
            await mark_deleted(session, row)
            retired += 1
            continue
        if cfg.get("seed") and slug not in CURRENT_SEED_SLUGS:
            await mark_deleted(session, row)
            retired += 1
    return retired


async def seed_tools_for_tenant(session: AsyncSession, tenant_id) -> tuple[int, int]:
    retired = await _retire_obsolete_seeds(session, tenant_id)
    created = 0
    for spec in SEED_CUSTOM_TOOLS:
        _, was_created = await _upsert_seed_tool(session, tenant_id, spec=spec)
        if was_created:
            created += 1
    await session.flush()
    return created, retired


async def seed_tools(session: AsyncSession) -> None:
    total_created = 0
    total_retired = 0
    for tenant_id in await list_tenant_ids(session):
        created, retired = await seed_tools_for_tenant(session, tenant_id)
        total_created += created
        total_retired += retired
    print(
        f">>> tools seed v{SEED_VERSION}: "
        f"created {total_created}, updated/kept {len(SEED_CUSTOM_TOOLS)} per tenant, "
        f"retired {total_retired} obsolete row(s)"
    )
