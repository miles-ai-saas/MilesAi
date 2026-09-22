"""
MCP 服务租户侧业务（L2）：CRUD、同步 tools_cache、试调用。

状态
----
- ``sync_service``：HTTP/SSE 调 ``fetch_mcp_tools``；STDIO 调 ``RunnerClient``
- ``invoke_tool``：工作台试调用；STDIO 经 Runner 沙箱
- ``stdio``：需 ``MCP_RUNNER_ENABLED=true`` 且 Runner 服务可达

远程协议在 ``tenant.mcp.client`` / ``sse_transport``；STDIO 在 ``runner.client``。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.config import get_settings
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_exec.mcp.constants import McpTransport
from miles_integrations.langchain.toolkit.naming import ident_collision
from miles_portal.tenant.mcp.client import fetch_mcp_tools
from miles_portal.tenant.mcp.client import invoke_mcp_tool as remote_invoke_mcp_tool
from miles_portal.tenant.mcp.meta import mcp_meta_dict
from miles_portal.tenant.mcp.models import McpService, McpStatus
from miles_portal.tenant.mcp.runner.audit import record_runner_session, write_mcp_runner_session
from miles_portal.tenant.mcp.runner.client import RunnerClient
from miles_portal.tenant.mcp.runner.spec_build import build_run_spec
from miles_portal.tenant.mcp.schemas.mcp import (
    McpServiceCreate,
    McpServiceOut,
    McpServiceUpdate,
    McpSyncResult,
    McpToolInvokeRequest,
    McpToolInvokeResult,
)
from miles_portal.tenant.mcp.schemas.meta import McpMetaOut
from miles_portal.tenant.mcp.transport import normalize_transport, transport_filter_values

STDIO_RUNNER_DISABLED = "STDIO 需要启用 MCP Runner（MCP_RUNNER_ENABLED=true），请联系管理员"


class McpServiceManager(BaseService):
    """MCP 注册表；endpoint 或 transport 变更后应重新 sync。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> McpMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return McpMetaOut.model_validate(mcp_meta_dict())

    def _resolve_endpoint(self, body: McpServiceCreate) -> tuple[str, str, dict]:
        """创建时解析 endpoint_url、归一化 transport 与 connection_config。"""
        transport = normalize_transport(body.transport)
        cfg = dict(body.connection_config or {})
        endpoint = (body.endpoint_url or "").strip()
        if transport == McpTransport.STDIO:
            command = str(cfg.get("command") or "").strip()
            if not command:
                raise BadRequestError("STDIO 需填写启动命令")
            if not endpoint:
                endpoint = f"stdio://{body.name.strip()}"
            return endpoint, transport.value, cfg
        if not endpoint:
            raise BadRequestError("HTTP/SSE 需填写端点 URL")
        cfg.setdefault("endpoint_url", endpoint)
        return endpoint, transport.value, cfg

    async def get_service(self, service_id: UUID) -> McpServiceOut:
        """读取服务详情；缺失/已删抛 ``NotFoundError``，跨租户拒绝访问。"""
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return McpServiceOut.model_validate(row)

    async def delete_service(self, service_id: UUID) -> None:
        """软删 MCP 服务。"""
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await mark_deleted(self.db, row)

    async def list_services(self, params: PageParams, transport_tab: str | None = None) -> PageResult[McpServiceOut]:
        """分页列出服务，可按 transport tab 过滤，按更新时间倒序。"""
        filters = [*tenant_filters(self.ctx, McpService.tenant_id), not_deleted(McpService)]
        values = transport_filter_values(transport_tab) if transport_tab else None
        if values:
            filters.append(McpService.transport.in_(values))
        total = await self.db.scalar(select(func.count(McpService.id)).where(*filters))
        stmt = select(McpService).where(*filters).order_by(McpService.updated_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[McpServiceOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def _assert_name_available(self, name: str, *, exclude_id: UUID | None = None) -> None:
        """校验该名称的工具标识在租户内未被其它服务占用。

        工具名（``mcp__{service}__{tool}``）是**运行期现算**的、不持久化，而派发按「重算 slug +
        全租户比对、取首个匹配」定位服务，故「同租户内 ident 唯一」是派发正确性的不变量。
        ident 由 ``service_ident`` 生成、本身不保证唯一（见其 docstring 的两处特性），
        这里在写入侧守住，使冲突在用户可改的地方被明确拒绝，而不是留到运行期静默误派发。
        """
        filters = [*tenant_filters(self.ctx, McpService.tenant_id), not_deleted(McpService)]
        if exclude_id is not None:
            filters.append(McpService.id != exclude_id)
        others = (await self.db.execute(select(McpService.name).where(*filters))).scalars().all()
        clash = ident_collision(name, others)
        if clash is not None:
            raise BadRequestError(f"服务名「{name}」的工具标识与已有服务「{clash}」相同，会导致工具调用落到另一个服务上，请改用其它名称")

    async def create_service(self, body: McpServiceCreate) -> McpServiceOut:
        """创建服务；endpoint/transport/connection_config 由 ``_resolve_endpoint`` 归一化。"""
        name = body.name.strip()
        await self._assert_name_available(name)
        endpoint, transport, cfg = self._resolve_endpoint(body)
        row = McpService(
            tenant_id=self.ctx.tenant_id,
            name=name,
            endpoint_url=endpoint,
            transport=transport,
            description=(body.description or "").strip() or None,
            connection_config=cfg,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return McpServiceOut.model_validate(row)

    async def update_service(self, service_id: UUID, body: McpServiceUpdate) -> McpServiceOut:
        """局部更新；切到 STDIO 时校验 command 并回填 ``stdio://`` endpoint。"""
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)

        if body.name is not None:
            new_name = body.name.strip()
            if new_name != row.name:
                await self._assert_name_available(new_name, exclude_id=service_id)
                row.name = new_name
        if body.description is not None:
            row.description = body.description.strip() or None
        if body.transport is not None:
            row.transport = normalize_transport(body.transport).value
        if body.connection_config is not None:
            row.connection_config = dict(body.connection_config)
        if body.endpoint_url is not None:
            row.endpoint_url = body.endpoint_url.strip()

        transport = normalize_transport(row.transport)
        if transport == McpTransport.STDIO:
            command = str((row.connection_config or {}).get("command") or "").strip()
            if not command:
                raise BadRequestError("STDIO 需填写启动命令")
            if not row.endpoint_url or row.endpoint_url.startswith("http"):
                row.endpoint_url = f"stdio://{row.name}"
        elif not row.endpoint_url:
            raise BadRequestError("HTTP/SSE 需填写端点 URL")

        await self.db.flush()
        await self.db.refresh(row)
        return McpServiceOut.model_validate(row)

    async def sync_service(self, service_id: UUID) -> McpSyncResult:
        """调用远端 tools/list，更新 tools_cache / last_sync_at / status / sync_error。"""
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)

        transport = normalize_transport(row.transport)
        if transport == McpTransport.STDIO:
            return await self._sync_stdio_service(row)

        try:
            tools = await fetch_mcp_tools(row.endpoint_url, transport, row.connection_config or {})
        except BadRequestError as e:
            row.sync_error = e.message
            row.status = McpStatus.ERROR
            await self.db.flush()
            raise
        now = datetime.now(UTC)
        if not tools:
            # 保留占位工具，便于 UI 展示失败原因而非空列表
            row.sync_error = "端点未返回工具列表（请确认 MCP 服务支持 tools/list）"
            row.status = McpStatus.ERROR
            row.tools_cache = [
                {
                    "name": f"{row.name}_placeholder",
                    "description": row.sync_error,
                }
            ]
            row.last_sync_at = now
            await self.db.flush()
            return McpSyncResult(tools=row.tools_cache, synced_at=now)

        row.tools_cache = tools
        row.last_sync_at = now
        row.status = McpStatus.ACTIVE
        row.sync_error = None
        await self.db.flush()
        return McpSyncResult(tools=tools, synced_at=now)

    async def _sync_stdio_service(self, row: McpService) -> McpSyncResult:
        settings = get_settings()
        if not settings.mcp_runner_enabled:
            row.sync_error = STDIO_RUNNER_DISABLED
            row.status = McpStatus.ERROR
            await self.db.flush()
            raise BadRequestError(STDIO_RUNNER_DISABLED)

        spec = build_run_spec(row, self.ctx, purpose="mcp_sync")
        try:
            async with record_runner_session(write_mcp_runner_session, self.db, spec=spec):
                tools = await RunnerClient().list_tools(spec, row.connection_config or {})
        except BadRequestError as e:
            row.sync_error = e.message
            row.status = McpStatus.ERROR
            await self.db.flush()
            raise

        now = datetime.now(UTC)
        if not tools:
            row.sync_error = "STDIO MCP 未返回工具列表"
            row.status = McpStatus.ERROR
            row.tools_cache = [
                {"name": f"{row.name}_placeholder", "description": row.sync_error},
            ]
            row.last_sync_at = now
            await self.db.flush()
            return McpSyncResult(tools=row.tools_cache, synced_at=now)

        row.tools_cache = tools
        row.last_sync_at = now
        row.status = McpStatus.ACTIVE
        row.sync_error = None
        await self.db.flush()
        return McpSyncResult(tools=tools, synced_at=now)

    async def invoke_tool(
        self,
        service_id: UUID,
        tool_name: str,
        body: McpToolInvokeRequest,
    ) -> McpToolInvokeResult:
        """试调用：工具名须在 tools_cache 中；按 row.transport 走 client.invoke_mcp_tool。"""
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        matched = next(
            (t for t in (row.tools_cache or []) if str(t.get("name")) == tool_name),
            None,
        )
        if not matched:
            raise NotFoundError(f"MCP 工具不存在: {tool_name}")

        transport = normalize_transport(row.transport)
        if transport == McpTransport.STDIO:
            settings = get_settings()
            if not settings.mcp_runner_enabled:
                raise BadRequestError(STDIO_RUNNER_DISABLED)
            spec = build_run_spec(row, self.ctx, purpose="mcp_invoke")
            async with record_runner_session(
                write_mcp_runner_session,
                self.db,
                spec=spec,
                tool_name=tool_name,
            ):
                output = await RunnerClient().call_tool(
                    spec,
                    tool_name,
                    body.params or {},
                    row.connection_config or {},
                )
            return McpToolInvokeResult(
                service_id=service_id,
                tool_name=tool_name,
                output=output,
            )

        output = await remote_invoke_mcp_tool(
            row.endpoint_url,
            tool_name,
            body.params,
            transport=transport,
            connection_config=row.connection_config or {},
        )
        return McpToolInvokeResult(
            service_id=service_id,
            tool_name=tool_name,
            output=output,
        )
