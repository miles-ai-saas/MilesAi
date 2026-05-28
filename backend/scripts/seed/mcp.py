"""租户 MCP 服务种子（多传输/状态场景，幂等）。

命令：``python cli.py seed mcp``
依赖：``seed tenant``（需已有租户）。

预置 ``tools_cache`` 便于工作台演示；真实调用需本地 MCP 或点击「同步」。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import not_deleted
from app.tenant.mcp.models import McpService, McpStatus

from scripts.seed._helpers import list_tenant_ids

# 与前端默认调试地址一致；用户可 PATCH 为实际端点
_LOCAL_HTTP = "http://127.0.0.1:3001/mcp"
_LOCAL_SSE = "http://127.0.0.1:3001/sse"

_TOOLS_FETCH = [
    {
        "name": "fetch",
        "description": "HTTP GET 抓取 URL 正文（Streamable HTTP 示例）",
    },
    {
        "name": "fetch_json",
        "description": "GET JSON API 并解析为结构化结果",
    },
]

_TOOLS_FILESYSTEM = [
    {"name": "read_file", "description": "读取允许目录内的文件内容"},
    {"name": "write_file", "description": "写入或覆盖文件"},
    {"name": "list_directory", "description": "列出目录条目"},
    {"name": "search_files", "description": "按 glob 搜索文件"},
]

_TOOLS_MEMORY = [
    {"name": "create_entities", "description": "在知识图谱中创建实体"},
    {"name": "create_relations", "description": "创建实体间关系"},
    {"name": "search_nodes", "description": "搜索节点"},
    {"name": "read_graph", "description": "读取当前图快照"},
]

_TOOLS_KB = [
    {
        "name": "search_documents",
        "description": "在已连接知识库中检索相关片段（演示用）",
    },
    {
        "name": "get_document",
        "description": "按 document_id 获取文档元数据与摘要",
    },
]

_NOW = datetime.now(timezone.utc)


def _cfg(**extra: object) -> dict:
    base = {"seed": True, "seed_version": 1}
    base.update(extra)
    return base


SEED_MCP_SERVICES: list[dict] = [
    {
        "name": "MCP示例·HTTP Streamable",
        "transport": "http",
        "endpoint_url": _LOCAL_HTTP,
        "description": "Streamable HTTP（单 URL POST JSON/SSE）。预置工具列表；需本地 MCP 后点「同步」或试调用。",
        "status": McpStatus.ACTIVE,
        "connection_config": _cfg(
            seed_scenario="http_streamable",
            timeout_sec=30,
            mcp_initialize=True,
        ),
        "tools_cache": _TOOLS_FETCH,
        "last_sync_at": _NOW,
        "sync_error": None,
    },
    {
        "name": "MCP示例·SSE Legacy",
        "transport": "sse",
        "endpoint_url": _LOCAL_SSE,
        "description": "Legacy SSE：GET 长连接收 endpoint 再 POST message。适合自建 MCP 网关 /sse 路径。",
        "status": McpStatus.ACTIVE,
        "connection_config": _cfg(
            seed_scenario="sse_legacy",
            timeout_sec=45,
            mcp_initialize=True,
        ),
        "tools_cache": _TOOLS_FILESYSTEM,
        "last_sync_at": _NOW,
        "sync_error": None,
    },
    {
        "name": "MCP示例·带鉴权 HTTP",
        "transport": "http",
        "endpoint_url": "https://mcp.example.com/v1/mcp",
        "description": "演示 connection_config.headers（Bearer）。端点为占位，请改为真实 URL 后同步。",
        "status": McpStatus.INACTIVE,
        "connection_config": _cfg(
            seed_scenario="http_auth",
            timeout_sec=30,
            headers={
                "Authorization": "Bearer <your-mcp-token>",
                "X-Tenant-Id": "demo",
            },
        ),
        "tools_cache": [],
        "last_sync_at": None,
        "sync_error": None,
    },
    {
        "name": "MCP示例·STDIO 文件系统",
        "transport": "stdio",
        "endpoint_url": "stdio://seed-filesystem",
        "description": "STDIO：npx @modelcontextprotocol/server-filesystem。需 MCP_RUNNER_ENABLED 与 Runner 服务。",
        "status": McpStatus.INACTIVE,
        "connection_config": _cfg(
            seed_scenario="stdio_filesystem",
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/tmp/milesai-mcp-demo",
            ],
            timeout_sec=60,
            network_mode="deny",
        ),
        "tools_cache": _TOOLS_FILESYSTEM,
        "last_sync_at": None,
        "sync_error": None,
    },
    {
        "name": "MCP示例·STDIO 记忆图谱",
        "transport": "stdio",
        "endpoint_url": "stdio://seed-memory",
        "description": "STDIO：官方 memory 服务。用于演示多 MCP 绑定与 Runner 沙箱命令白名单。",
        "status": McpStatus.INACTIVE,
        "connection_config": _cfg(
            seed_scenario="stdio_memory",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            timeout_sec=45,
            env={"NODE_ENV": "production"},
            network_mode="deny",
        ),
        "tools_cache": _TOOLS_MEMORY,
        "last_sync_at": None,
        "sync_error": None,
    },
    {
        "name": "MCP示例·同步失败",
        "transport": "http",
        "endpoint_url": "http://127.0.0.1:59999/mcp",
        "description": "演示 status=error 与 sync_error 展示（不可达端口）。可编辑端点后重新同步。",
        "status": McpStatus.ERROR,
        "connection_config": _cfg(
            seed_scenario="sync_error",
            timeout_sec=5,
        ),
        "tools_cache": [],
        "last_sync_at": _NOW,
        "sync_error": "连接被拒绝：127.0.0.1:59999（种子演示用不可达端点）",
    },
    {
        "name": "MCP示例·待同步",
        "transport": "sse",
        "endpoint_url": _LOCAL_SSE,
        "description": "新建后尚未成功同步（空 tools_cache）。用于测试列表筛选与首次同步流程。",
        "status": McpStatus.INACTIVE,
        "connection_config": _cfg(
            seed_scenario="pending_sync",
            mcp_initialize=True,
        ),
        "tools_cache": [],
        "last_sync_at": None,
        "sync_error": None,
    },
    {
        "name": "MCP示例·知识检索",
        "transport": "http",
        "endpoint_url": _LOCAL_HTTP,
        "description": "预置检索类工具名，便于智能体 config.mcp_service_ids 绑定演示。",
        "status": McpStatus.ACTIVE,
        "connection_config": _cfg(
            seed_scenario="kb_tools",
            timeout_sec=30,
            session_id="seed-demo-session",
        ),
        "tools_cache": _TOOLS_KB,
        "last_sync_at": _NOW,
        "sync_error": None,
    },
]

_UPDATABLE = (
    "endpoint_url",
    "transport",
    "description",
    "connection_config",
    "tools_cache",
    "last_sync_at",
    "sync_error",
    "status",
)


async def _upsert_mcp_service(
    session: AsyncSession,
    tenant_id,
    spec: dict,
) -> tuple[McpService, bool]:
    name = spec["name"]
    row = await session.scalar(
        select(McpService).where(
            McpService.tenant_id == tenant_id,
            McpService.name == name,
            not_deleted(McpService),
        )
    )
    created = row is None
    if not row:
        row = McpService(
            tenant_id=tenant_id,
            name=name,
            endpoint_url=spec["endpoint_url"],
            transport=spec["transport"],
            description=spec.get("description"),
            connection_config=spec.get("connection_config") or {},
            tools_cache=spec.get("tools_cache") or [],
            last_sync_at=spec.get("last_sync_at"),
            sync_error=spec.get("sync_error"),
            status=spec.get("status") or McpStatus.INACTIVE,
        )
        session.add(row)
    else:
        for key in _UPDATABLE:
            if key in spec:
                setattr(row, key, spec[key])
    await session.flush()
    await session.refresh(row)
    return row, created


async def seed_mcp_for_tenant(session: AsyncSession, tenant_id) -> int:
    created = 0
    for spec in SEED_MCP_SERVICES:
        _, was_created = await _upsert_mcp_service(session, tenant_id, spec)
        if was_created:
            created += 1
    await session.flush()
    return created


async def seed_mcp(session: AsyncSession) -> None:
    total_created = 0
    tenants = await list_tenant_ids(session)
    if not tenants:
        print(">>> mcp seed: skip (no tenants, run seed tenant first)")
        return
    for tenant_id in tenants:
        total_created += await seed_mcp_for_tenant(session, tenant_id)
    print(f">>> mcp seed: {len(SEED_MCP_SERVICES)} scenario(s) per tenant, created {total_created} new row(s) across {len(tenants)} tenant(s)")
