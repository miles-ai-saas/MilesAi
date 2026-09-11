"""
工具注册表（L2）：内置 registry、租户自定义 HTTP 工具。

catalog
-------
合并 ``BUILTIN_REGISTRY`` 与 DB ``Tool`` 行（**不含 MCP**，MCP 见 ``tenant.mcp``）。

执行
----
``invoke_tool_with_context`` → ``tenant.tools.invoke``（内置含 ``knowledge_search`` → ``search_kb``）。

与 Agent：``enable_tool_calling`` 时走 ``integrations.langchain.tool_agent``，非本 Service 直连。
与 MCP：独立模块；关系见 ``docs/guides/tools.md`` §6。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.url_security import validate_outbound_url
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.meta.category import CategoryDomain
from app.tenant.categories.services.category import CategoryService
from app.models.meta.tag import TagEntityType
from app.tenant.tags.schemas.tag import TagRefOut
from app.tenant.tags.services.tag import TagService
from app.integrations.langchain.tools import is_mcp_tool_name
from app.tenant.tools.builtin_registry import BUILTIN_REGISTRY, BUILTIN_SLUGS
from app.tenant.tools.confirmation import ToolConfirmationRequired
from app.tenant.tools.invoke import invoke_tool_with_context
from app.tenant.tools.models import Tool, ToolInvocationLog, ToolType
from app.core.config import get_settings
from app.tenant.tools.parameters import normalize_parameters
from app.exec.sandbox.validate import validate_script_source
from app.common.schema import PageParams, PageResult
from app.tenant.tools.schemas.tools import (
    ToolCatalogItem,
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResult,
    ToolInvocationLogOut,
    ToolOut,
    ToolUpdate,
    PendingToolCall,
)
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService


def _tool_source_of(name: str, *, has_tool_id: bool = False) -> str:
    """试调用结果来源标注：builtin / custom / mcp。"""
    if is_mcp_tool_name(name):
        return "mcp"
    if name in BUILTIN_SLUGS and not has_tool_id:
        return "builtin"
    return "custom"


class ToolsService(BaseService):
    """租户工具 CRUD、目录与试跑 invoke。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self):
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        from app.tenant.tools.meta import tools_meta_dict
        from app.tenant.tools.schemas.meta import ToolsMetaOut

        return ToolsMetaOut.model_validate(tools_meta_dict())

    async def list_tools(
        self,
        params: PageParams,
        *,
        category_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[ToolOut]:
        """分页列出当前租户工具，可按分类/标签过滤，按创建时间倒序。"""
        filters = append_not_deleted(tenant_filters(self.ctx, Tool.tenant_id), Tool)
        if category_id:
            filters.append(Tool.category_id == category_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.TOOL, tag_ids or [])
        if tag_subq is not None:
            filters.append(Tool.id.in_(tag_subq))
        total = await self.db.scalar(select(func.count(Tool.id)).where(*filters))
        stmt = select(Tool).where(*filters).order_by(Tool.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        names = await self._category_names({t.category_id for t in items if t.category_id})
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.TOOL, {t.id for t in items})
        return PageResult(
            items=[self._to_out(t, names.get(t.category_id), tags_map.get(t.id, [])) for t in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def get_tool(self, tool_id: UUID) -> ToolOut:
        """按 ID 取工具详情（含 category_name 与标签）。"""
        row = await self._get_or_raise(tool_id)
        cat_name = await self._category_name(row.category_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.TOOL, {row.id})
        return self._to_out(row, cat_name, tags_map.get(row.id, []))

    def _normalize_script_config(self, config: dict | None) -> dict:
        cfg = dict(config or {})
        source = validate_script_source(str(cfg.get("source") or ""))
        timeout = min(max(int(cfg.get("timeout_sec") or 30), 1), 120)
        memory = min(max(int(cfg.get("max_memory_mb") or 512), 128), 2048)
        return {
            "language": "python",
            "source": source,
            "timeout_sec": timeout,
            "max_memory_mb": memory,
        }

    async def create_tool(self, body: ToolCreate) -> ToolOut:
        """创建工具；校验内置 slug 冲突、出站 URL 安全与脚本沙箱开关。"""
        if body.tool_type == ToolType.SCRIPT:
            if not get_settings().mcp_runner_enabled:
                raise BadRequestError("脚本工具需要启用 MCP Runner（MCP_RUNNER_ENABLED=true）")
        if body.slug in BUILTIN_SLUGS:
            raise BadRequestError(f"slug「{body.slug}」与内置工具冲突")
        await self._ensure_slug_unique(body.slug)
        params = normalize_parameters([p.model_dump() for p in body.parameters])
        config = body.config
        if body.tool_type == ToolType.HTTP:
            url = (config or {}).get("url")
            if not url:
                raise BadRequestError("HTTP 工具须配置 config.url")
            validate_outbound_url(str(url))
        elif body.tool_type == ToolType.SCRIPT:
            config = self._normalize_script_config(config)
        if body.category_id:
            await CategoryService(self.db, self.ctx).validate_category_for_domain(body.category_id, CategoryDomain.TOOL)
        row = Tool(
            tenant_id=self.ctx.tenant_id,
            slug=body.slug.strip(),
            name=body.name.strip(),
            description=body.description,
            tool_type=body.tool_type,
            category_id=body.category_id,
            version=body.version,
            require_confirmation=body.require_confirmation,
            parameters=params,
            config=config,
        )
        self.db.add(row)
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.TOOL, row.id, body.tag_ids)
        await self.db.refresh(row)
        cat_name = await self._category_name(row.category_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.TOOL, {row.id})
        return self._to_out(row, cat_name, tags_map.get(row.id, []))

    async def update_tool(self, tool_id: UUID, body: ToolUpdate) -> ToolOut:
        """局部更新；改 slug/config 时重新做冲突与 URL/脚本校验。"""
        row = await self._get_or_raise(tool_id)
        data = body.model_dump(exclude_unset=True)
        tag_ids = data.pop("tag_ids", None)
        if "slug" in data and data["slug"]:
            if data["slug"] in BUILTIN_SLUGS:
                raise BadRequestError(f"slug「{data['slug']}」与内置工具冲突")
            await self._ensure_slug_unique(data["slug"], exclude_id=tool_id)
        if "parameters" in data and data["parameters"] is not None:
            data["parameters"] = normalize_parameters(data["parameters"])
        if "category_id" in data and data["category_id"]:
            await CategoryService(self.db, self.ctx).validate_category_for_domain(data["category_id"], CategoryDomain.TOOL)
        if "config" in data and data["config"] is not None:
            if row.tool_type == ToolType.SCRIPT or data.get("tool_type") == ToolType.SCRIPT:
                if not get_settings().mcp_runner_enabled:
                    raise BadRequestError("脚本工具需要启用 MCP Runner（MCP_RUNNER_ENABLED=true）")
                data["config"] = self._normalize_script_config(data["config"])
            else:
                url = data["config"].get("url")
                if url:
                    validate_outbound_url(str(url))
        for k, v in data.items():
            setattr(row, k, v)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.TOOL, row.id, tag_ids)
        await self.db.refresh(row)
        cat_name = await self._category_name(row.category_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.TOOL, {row.id})
        return self._to_out(row, cat_name, tags_map.get(row.id, []))

    async def delete_tool(self, tool_id: UUID) -> None:
        """软删工具并清理其标签关联。"""
        row = await self._get_or_raise(tool_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.TOOL, row.id)
        await mark_deleted(self.db, row)

    async def invoke(self, name: str, body: ToolInvokeRequest) -> ToolInvokeResult:
        """试调用工具；需确认时返回 ``confirmation_required`` 与待确认信息，不实际执行。"""
        try:
            output = await invoke_tool_with_context(
                self.db,
                self.ctx,
                name,
                body.params,
                tool_id=body.tool_id,
                confirmed=body.confirmed,
                actor_user_id=self.ctx.user_id,
                invoke_source="api",
            )
        except ToolConfirmationRequired as exc:
            source = _tool_source_of(exc.slug)
            return ToolInvokeResult(
                tool=exc.slug,
                source=source,
                status="confirmation_required",
                pending=PendingToolCall(
                    slug=exc.slug,
                    name=exc.tool_name,
                    description=exc.tool_description,
                    params=exc.params,
                ),
            )
        source = _tool_source_of(name, has_tool_id=bool(body.tool_id))
        return ToolInvokeResult(tool=name, source=source, status="success", output=output)

    async def list_invocation_logs(self, params: PageParams, *, tool_slug: str | None = None) -> PageResult[ToolInvocationLogOut]:
        """分页查询调用日志，可按工具 slug 过滤，按创建时间倒序。"""
        filters = [ToolInvocationLog.tenant_id == self.ctx.tenant_id]
        if tool_slug:
            filters.append(ToolInvocationLog.tool_slug == tool_slug)
        total = await self.db.scalar(select(func.count(ToolInvocationLog.id)).where(*filters))
        stmt = (
            select(ToolInvocationLog).where(*filters).order_by(ToolInvocationLog.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[ToolInvocationLogOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def list_catalog(
        self,
        *,
        source: str | None = None,
        category_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> list[ToolCatalogItem]:
        """合并内置与租户工具为目录；``source`` 仅接受 builtin/custom（MCP 不在此）。"""
        from app.models.meta.category import SysCategory

        cat_rows = (
            await self.db.execute(
                select(SysCategory.id, SysCategory.slug, SysCategory.name).where(
                    SysCategory.domain == CategoryDomain.TOOL.value,
                    not_deleted(SysCategory),
                )
            )
        ).all()
        slug_to_id = {r[1]: r[0] for r in cat_rows}
        id_to_name = {r[0]: r[2] for r in cat_rows}
        category_slug: str | None = None
        if category_id:
            for cid, slug, _ in cat_rows:
                if cid == category_id:
                    category_slug = slug
                    break

        catalog: list[ToolCatalogItem] = []
        src = (source or "").strip().lower()

        if not src or src == "builtin":
            for t in BUILTIN_REGISTRY:
                cat_slug = t.get("category_slug", "general")
                if category_slug and cat_slug != category_slug:
                    continue
                cat_id = slug_to_id.get(cat_slug)
                catalog.append(
                    ToolCatalogItem(
                        source="builtin",
                        slug=t["slug"],
                        name=t["name"],
                        description=t.get("description"),
                        category_id=cat_id,
                        category_name=id_to_name.get(cat_id) if cat_id else None,
                        parameters=t.get("parameters") or [],
                        version=t.get("version"),
                        require_confirmation=bool(t.get("require_confirmation")),
                    )
                )

        if not src or src == "custom":
            filters = append_not_deleted(
                tenant_filters(self.ctx, Tool.tenant_id),
                Tool,
            )
            if category_id:
                filters.append(Tool.category_id == category_id)
            tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.TOOL, tag_ids or [])
            if tag_subq is not None:
                filters.append(Tool.id.in_(tag_subq))
            custom = (await self.db.execute(select(Tool).where(*filters, Tool.is_active.is_(True)).order_by(Tool.slug))).scalars().all()
            for t in custom:
                catalog.append(
                    ToolCatalogItem(
                        source="custom",
                        slug=t.slug,
                        name=t.name,
                        description=t.description,
                        category_id=t.category_id,
                        category_name=id_to_name.get(t.category_id) if t.category_id else None,
                        parameters=t.parameters or [],
                        version=t.version,
                        require_confirmation=t.require_confirmation,
                        tool_id=t.id,
                        tool_type=t.tool_type.value if hasattr(t.tool_type, "value") else str(t.tool_type),
                        updated_at=t.updated_at,
                    )
                )

        if src and src not in ("builtin", "custom"):
            raise BadRequestError("source 须为 builtin 或 custom")

        return catalog

    async def list_builtin(self) -> list[dict]:
        """返回内置工具注册表原始定义。"""
        return BUILTIN_REGISTRY

    async def _get_or_raise(self, tool_id: UUID) -> Tool:
        row = await self.db.get(Tool, tool_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("工具不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _ensure_slug_unique(self, slug: str, *, exclude_id: UUID | None = None) -> None:
        filters = [
            Tool.tenant_id == self.ctx.tenant_id,
            Tool.slug == slug,
            not_deleted(Tool),
        ]
        if exclude_id:
            filters.append(Tool.id != exclude_id)
        exists = await self.db.scalar(select(Tool.id).where(*filters).limit(1))
        if exists:
            raise ConflictError(f"工具编号「{slug}」已存在")

    async def _category_names(self, ids: set[UUID]) -> dict[UUID, str]:
        return await CategoryService(self.db, self.ctx).get_category_name_map(CategoryDomain.TOOL, ids)

    async def _category_name(self, category_id: UUID | None) -> str | None:
        if not category_id:
            return None
        return (await self._category_names({category_id})).get(category_id)

    @staticmethod
    def _to_out(
        row: Tool,
        category_name: str | None,
        tags: list[TagRefOut] | None = None,
    ) -> ToolOut:
        data = ToolOut.model_validate(row)
        return data.model_copy(update={"category_name": category_name, "tags": tags or []})
