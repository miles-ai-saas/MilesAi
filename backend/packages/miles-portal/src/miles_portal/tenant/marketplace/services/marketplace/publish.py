"""应用市场上架方：创建、编辑、提交审核。"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_portal.marketplace.review_config import get_marketplace_review_mode
from miles_core.models.agent import Agent
from miles_core.models.flow import Flow
from miles_core.models.kb import KnowledgeBase
from miles_portal.tenant.marketplace.models import AppCategory, MarketplaceApp, MarketplaceAppStatus
from miles_portal.tenant.marketplace.schemas.marketplace import (
    MarketplaceAppCreate,
    MarketplaceAppCreateFromResources,
    MarketplaceAppOut,
    MarketplaceAppUpdate,
)
from miles_core.models.meta.tag import TagEntityType
from miles_portal.tenant.marketplace.util import load_flow_template_graph
from miles_portal.tenant.tags.services.tag import TagService


class MarketplacePublishMixin:
    """应用创建、编辑、manifest 与提交审核。"""

    async def build_manifest_from_resources(self, body: MarketplaceAppCreateFromResources) -> dict:
        """从 KB/Flow/Agent 资源生成安装 manifest。"""
        resources: dict = {}
        if body.kb_id:
            kb = await self.db.get(KnowledgeBase, body.kb_id)
            if not kb or kb.tenant_id != self.ctx.tenant_id:
                raise NotFoundError("知识库不存在")
            resources["knowledge_base"] = {
                "name": kb.name,
                "description": kb.description or body.description,
            }
        if body.flow_id:
            flow = await self.db.get(Flow, body.flow_id)
            if not flow or flow.tenant_id != self.ctx.tenant_id:
                raise NotFoundError("流程不存在")
            graph_json = load_flow_template_graph("rag")
            if flow.current_version > 0:
                version = await self.flow_repo.get_version(body.flow_id, flow.current_version)
                if version and version.graph_json:
                    graph_json = version.graph_json
            resources["flow"] = {
                "name": flow.name,
                "description": flow.description,
                "graph_json": graph_json,
                "auto_publish": False,
            }
        if body.agent_id:
            agent = await self.db.get(Agent, body.agent_id)
            if not agent or agent.tenant_id != self.ctx.tenant_id:
                raise NotFoundError("智能体不存在")
            resources["agent"] = {
                "name": agent.name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "bind_kb": body.kb_id is not None,
                "bind_flow": body.flow_id is not None,
            }
        if not resources:
            raise BadRequestError("请至少选择知识库、流程或智能体之一")
        return {"version": "1.0.0", "resources": resources}

    async def create_app_from_resources(self, body: MarketplaceAppCreateFromResources) -> MarketplaceAppOut:
        """从已有资源创建草稿应用。"""
        manifest = await self.build_manifest_from_resources(body)
        return await self.create_app(
            MarketplaceAppCreate(
                name=body.name,
                description=body.description,
                icon=body.icon,
                category_slug=body.category_slug,
                manifest=manifest,
                status=MarketplaceAppStatus.DRAFT,
                tag_ids=body.tag_ids,
                visibility=body.visibility,
            )
        )

    async def create_app(self, body: MarketplaceAppCreate) -> MarketplaceAppOut:
        """创建市场应用（草稿）。"""
        category_id = None
        if body.category_slug:
            cat = await self.db.scalar(select(AppCategory).where(AppCategory.slug == body.category_slug))
            if cat:
                category_id = cat.id
        app = MarketplaceApp(
            publisher_tenant_id=self.ctx.tenant_id,
            category_id=category_id,
            name=body.name,
            description=body.description,
            icon=body.icon,
            version=body.version,
            status=body.status,
            is_official=False,
            manifest=body.manifest,
            visibility=body.visibility.value,
        )
        self.db.add(app)
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.MARKETPLACE_APP, app.id, body.tag_ids)
        await self.db.refresh(app, ["category"])
        return await self.app_out_with_tags(app)

    async def update_app(self, app_id: UUID, body: MarketplaceAppUpdate) -> MarketplaceAppOut:
        """更新应用（禁止直接改上架/待审状态）。"""
        app = await self.get_own_app_or_raise(app_id)
        if app.is_official:
            raise BadRequestError("官方应用不可编辑")
        data = body.model_dump(exclude_unset=True)
        new_status = data.get("status")
        if new_status in (
            MarketplaceAppStatus.PUBLISHED,
            MarketplaceAppStatus.PENDING_REVIEW,
        ):
            raise BadRequestError("请使用「提交审核」上架，不可直接修改为上架或待审状态")
        category_slug = data.pop("category_slug", None)
        tag_ids = data.pop("tag_ids", None)
        if category_slug is not None:
            cat = await self.db.scalar(select(AppCategory).where(AppCategory.slug == category_slug))
            app.category_id = cat.id if cat else None
        for key, value in data.items():
            setattr(app, key, value)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.MARKETPLACE_APP, app.id, tag_ids)
        await self.db.refresh(app, ["category"])
        return await self.app_out_with_tags(app)

    def validate_manifest(self, manifest: dict) -> None:
        """校验 manifest 至少含一种可安装资源。"""
        resources = manifest.get("resources") or manifest
        if not any(resources.get(k) for k in ("flow", "agent", "knowledge_base")):
            raise BadRequestError("manifest 需包含 flow、agent 或 knowledge_base 至少一项")

    async def publish_app(self, app_id: UUID) -> MarketplaceAppOut:
        """提交审核（原 publish 路径保留）。"""
        app = await self.get_own_app_or_raise(app_id)
        if app.is_official:
            raise BadRequestError("官方应用无需发布")
        if app.status not in (
            MarketplaceAppStatus.DRAFT,
            MarketplaceAppStatus.REJECTED,
        ):
            raise BadRequestError("仅草稿或已驳回的应用可提交审核")
        self.validate_manifest(app.manifest or {})
        mode = await get_marketplace_review_mode(self.db)
        app.submitted_at = datetime.now(timezone.utc)
        app.review_note = None
        app.reviewed_at = None
        app.reviewed_by = None
        app.reviewed_by_admin_id = None
        app.reviewer_type = None
        if mode == "off":
            app.status = MarketplaceAppStatus.PUBLISHED
        else:
            app.status = MarketplaceAppStatus.PENDING_REVIEW
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        return await self.app_out_with_tags(app)
