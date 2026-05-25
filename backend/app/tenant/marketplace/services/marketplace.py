"""应用市场：上架、审核、安装（克隆 KB/Flow/Agent 到本租户）与评分。

安装走 install_app：按 manifest 在本租户 create_kb/create_flow/create_agent；
审核 approve/reject 需平台权限；卸载见 deletion 与 AppInstall 级联（若有 API）。
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.tenant import TenantContext, tenant_filters
from app.tenant.marketplace.models import (
    AppCategory,
    AppInstall,
    AppRating,
    MarketplaceApp,
    MarketplaceAppStatus,
)
from app.core.soft_delete import mark_deleted, not_deleted
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.flows.repositories.flow import FlowRepository
from app.tenant.kb.repositories.kb import KnowledgeBaseRepository
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.kb import KnowledgeBase
from app.tenant.agents.schemas.agent import AgentCreate
from app.common.schema import PageParams, PageResult
from app.tenant.flows.schemas.flow import FlowCreate
from app.tenant.kb.schemas.kb import KnowledgeBaseCreate
from app.tenant.marketplace.schemas.marketplace import (
    AppCategoryOut,
    AppInstallOut,
    AppInstallResult,
    AppRatingCreate,
    AppRatingOut,
    MarketplaceAppCreate,
    MarketplaceAppCreateFromResources,
    MarketplaceAppDetail,
    MarketplaceAppOut,
    MarketplaceAppUpdate,
)
from app.tenant.marketplace.util import load_rag_graph_template
from app.tenant.agents.services.agent import AgentService
from app.core.service import BaseService
from app.tenant.flows.services.flow import FlowService
from app.tenant.kb.services.kb import KnowledgeBaseService


class MarketplaceService(BaseService):
    """安装时按 manifest 深拷贝资源；卸载走 deletion.cascade 解除 AppInstall 引用。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.flow_repo = FlowRepository(db)
        self.agent_repo = AgentRepository(db)
        self.kb_repo = KnowledgeBaseRepository(db)

    async def list_categories(self) -> list[AppCategoryOut]:
        stmt = select(AppCategory).order_by(AppCategory.sort_order.asc(), AppCategory.name.asc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [AppCategoryOut.model_validate(r) for r in rows]

    async def _installed_app_ids(self) -> set[UUID]:
        stmt = select(AppInstall.app_id).where(AppInstall.tenant_id == self.ctx.tenant_id)
        return set((await self.db.execute(stmt)).scalars().all())

    def _app_out(self, app: MarketplaceApp, *, installed: bool, category_name: str | None) -> MarketplaceAppOut:
        return MarketplaceAppOut(
            id=app.id,
            name=app.name,
            description=app.description,
            icon=app.icon,
            version=app.version,
            status=app.status,
            is_official=app.is_official,
            install_count=app.install_count,
            rating_avg=round(float(app.rating_avg or 0), 2),
            rating_count=int(app.rating_count or 0),
            category_id=app.category_id,
            category_name=category_name,
            installed=installed,
            review_note=app.review_note,
            submitted_at=app.submitted_at,
            reviewed_at=app.reviewed_at,
            created_at=app.created_at,
        )

    async def _refresh_rating_stats(self, app_id: UUID) -> None:
        stmt = select(
            func.avg(AppRating.score),
            func.count(AppRating.id),
        ).where(AppRating.app_id == app_id, not_deleted(AppRating))
        avg_score, count = (await self.db.execute(stmt)).one()
        app = await self._get_app_or_raise(app_id)
        app.rating_avg = round(float(avg_score or 0), 2)
        app.rating_count = int(count or 0)
        await self.db.flush()

    async def _require_installed(self, app_id: UUID) -> None:
        installed = await self.db.scalar(
            select(AppInstall.id).where(
                AppInstall.tenant_id == self.ctx.tenant_id,
                AppInstall.app_id == app_id,
            )
        )
        if not installed:
            raise BadRequestError("安装该应用后才可评分")

    async def list_apps(
        self,
        params: PageParams,
        *,
        category_slug: str | None = None,
        sort: str = "installs",
    ) -> PageResult[MarketplaceAppOut]:
        installed_ids = await self._installed_app_ids()
        stmt = (
            select(MarketplaceApp)
            .where(MarketplaceApp.status == MarketplaceAppStatus.PUBLISHED)
            .options(selectinload(MarketplaceApp.category))
        )
        count_filters = [MarketplaceApp.status == MarketplaceAppStatus.PUBLISHED]
        if category_slug:
            stmt = stmt.join(AppCategory, MarketplaceApp.category_id == AppCategory.id).where(
                AppCategory.slug == category_slug
            )
            count_filters.append(AppCategory.slug == category_slug)
        count_stmt = select(func.count(MarketplaceApp.id)).where(*count_filters)
        if category_slug:
            count_stmt = count_stmt.join(
                AppCategory, MarketplaceApp.category_id == AppCategory.id
            )
        total = await self.db.scalar(count_stmt)
        if sort == "rating":
            stmt = stmt.order_by(
                MarketplaceApp.rating_avg.desc(),
                MarketplaceApp.rating_count.desc(),
                MarketplaceApp.install_count.desc(),
            )
        else:
            stmt = stmt.order_by(MarketplaceApp.install_count.desc())
        stmt = stmt.offset(
            (params.page - 1) * params.size
        ).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        items = [
            self._app_out(
                a,
                installed=a.id in installed_ids,
                category_name=a.category.name if a.category else None,
            )
            for a in apps
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def get_app(self, app_id: UUID) -> MarketplaceAppDetail:
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            if app.publisher_tenant_id != self.ctx.tenant_id:
                raise NotFoundError("应用不存在或未发布")
        installed_ids = await self._installed_app_ids()
        cat_name = app.category.name if app.category else None
        base = self._app_out(app, installed=app.id in installed_ids, category_name=cat_name)
        my_rating = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        return MarketplaceAppDetail(
            **base.model_dump(),
            manifest=app.manifest or {},
            my_rating=AppRatingOut.model_validate(my_rating) if my_rating else None,
        )

    async def _get_app_or_raise(self, app_id: UUID) -> MarketplaceApp:
        stmt = (
            select(MarketplaceApp)
            .where(MarketplaceApp.id == app_id)
            .options(selectinload(MarketplaceApp.category))
        )
        app = (await self.db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise NotFoundError("应用不存在")
        return app

    async def list_my_apps(self, params: PageParams) -> PageResult[MarketplaceAppOut]:
        installed_ids = await self._installed_app_ids()
        filters = [MarketplaceApp.publisher_tenant_id == self.ctx.tenant_id]
        stmt = (
            select(MarketplaceApp)
            .where(*filters)
            .options(selectinload(MarketplaceApp.category))
            .order_by(MarketplaceApp.updated_at.desc())
        )
        count_stmt = select(func.count(MarketplaceApp.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        items = [
            self._app_out(
                a,
                installed=a.id in installed_ids,
                category_name=a.category.name if a.category else None,
            )
            for a in apps
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def _get_own_app_or_raise(self, app_id: UUID) -> MarketplaceApp:
        app = await self._get_app_or_raise(app_id)
        if app.publisher_tenant_id != self.ctx.tenant_id:
            raise NotFoundError("应用不存在")
        return app

    async def _build_manifest_from_resources(
        self, body: MarketplaceAppCreateFromResources
    ) -> dict:
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
            graph_json = load_rag_graph_template()
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

    async def create_app_from_resources(
        self, body: MarketplaceAppCreateFromResources
    ) -> MarketplaceAppOut:
        manifest = await self._build_manifest_from_resources(body)
        return await self.create_app(
            MarketplaceAppCreate(
                name=body.name,
                description=body.description,
                icon=body.icon,
                category_slug=body.category_slug,
                manifest=manifest,
                status=MarketplaceAppStatus.DRAFT,
            )
        )

    async def create_app(self, body: MarketplaceAppCreate) -> MarketplaceAppOut:
        category_id = None
        if body.category_slug:
            cat = await self.db.scalar(
                select(AppCategory).where(AppCategory.slug == body.category_slug)
            )
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
        )
        self.db.add(app)
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        return self._app_out(
            app,
            installed=False,
            category_name=app.category.name if app.category else None,
        )

    async def update_app(self, app_id: UUID, body: MarketplaceAppUpdate) -> MarketplaceAppOut:
        app = await self._get_own_app_or_raise(app_id)
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
        if category_slug is not None:
            cat = await self.db.scalar(
                select(AppCategory).where(AppCategory.slug == category_slug)
            )
            app.category_id = cat.id if cat else None
        for key, value in data.items():
            setattr(app, key, value)
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self._installed_app_ids()
        return self._app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )

    def _validate_manifest(self, manifest: dict) -> None:
        resources = manifest.get("resources") or manifest
        if not any(resources.get(k) for k in ("flow", "agent", "knowledge_base")):
            raise BadRequestError("manifest 需包含 flow、agent 或 knowledge_base 至少一项")

    async def publish_app(self, app_id: UUID) -> MarketplaceAppOut:
        """提交审核（原 publish 路径保留）。"""
        app = await self._get_own_app_or_raise(app_id)
        if app.is_official:
            raise BadRequestError("官方应用无需发布")
        if app.status not in (
            MarketplaceAppStatus.DRAFT,
            MarketplaceAppStatus.REJECTED,
        ):
            raise BadRequestError("仅草稿或已驳回的应用可提交审核")
        self._validate_manifest(app.manifest or {})
        app.status = MarketplaceAppStatus.PENDING_REVIEW
        app.submitted_at = datetime.now(timezone.utc)
        app.review_note = None
        app.reviewed_at = None
        app.reviewed_by = None
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self._installed_app_ids()
        return self._app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )

    async def install_app(self, app_id: UUID) -> AppInstallResult:
        """将已发布应用快照复制到当前租户（KB、流程、智能体等）。"""
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise BadRequestError("应用未发布，无法安装")

        existing = await self.db.scalar(
            select(AppInstall).where(
                AppInstall.tenant_id == self.ctx.tenant_id,
                AppInstall.app_id == app_id,
            )
        )
        if existing:
            raise ConflictError("该应用已安装，可在「我的安装」中查看")

        manifest = app.manifest or {}
        resources = manifest.get("resources") or manifest
        flow_id: UUID | None = None
        agent_id: UUID | None = None
        kb_id: UUID | None = None

        kb_svc = KnowledgeBaseService(self.db, self.ctx)
        flow_svc = FlowService(self.db, self.ctx)
        agent_svc = AgentService(self.db, self.ctx)

        kb_spec = resources.get("knowledge_base")
        if kb_spec:
            suffix = str(self.ctx.tenant_id)[:8]
            kb = await kb_svc.create_kb(
                KnowledgeBaseCreate(
                    name=kb_spec.get("name", f"{app.name} 知识库"),
                    description=kb_spec.get("description", f"来自应用市场：{app.name}"),
                )
            )
            kb_id = kb.id

        flow_spec = resources.get("flow")
        if flow_spec:
            graph = flow_spec.get("graph_json") or load_rag_graph_template()
            flow = await flow_svc.create_flow(
                FlowCreate(
                    name=flow_spec.get("name", f"{app.name} 流程"),
                    description=flow_spec.get("description"),
                    graph_json=graph,
                )
            )
            flow_id = flow.id
            if flow_spec.get("auto_publish", True):
                await flow_svc.publish(flow_id)

        agent_spec = resources.get("agent")
        if agent_spec:
            bind_kb = agent_spec.get("bind_kb", True) and kb_id is not None
            bind_flow = agent_spec.get("bind_flow", True) and flow_id is not None
            agent = await agent_svc.create_agent(
                AgentCreate(
                    name=agent_spec.get("name", f"{app.name} 助手"),
                    description=agent_spec.get("description", app.description),
                    system_prompt=agent_spec.get(
                        "system_prompt",
                        "你是企业知识库助手，请基于检索内容准确回答用户问题。",
                    ),
                    published_flow_id=flow_id if bind_flow else None,
                    kb_ids=[kb_id] if bind_kb else [],
                    config=agent_spec.get("config") or {},
                )
            )
            agent_id = agent.id

        if not any([flow_id, agent_id, kb_id]):
            raise BadRequestError("应用模板未定义可安装资源（flow/agent/knowledge_base）")

        install = AppInstall(
            tenant_id=self.ctx.tenant_id,
            app_id=app.id,
            installed_by=self.ctx.user_id,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
        )
        self.db.add(install)
        app.install_count += 1
        await self.db.flush()
        await self.db.refresh(install)

        install_out = AppInstallOut(
            id=install.id,
            app_id=app.id,
            app_name=app.name,
            tenant_id=install.tenant_id,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
            created_at=install.created_at,
        )
        return AppInstallResult(
            install=install_out,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
            message="安装成功，已创建关联资源",
        )

    async def list_installs(self, params: PageParams) -> PageResult[AppInstallOut]:
        filters = tenant_filters(self.ctx, AppInstall.tenant_id)
        stmt = (
            select(AppInstall)
            .where(*filters)
            .options(selectinload(AppInstall.app))
            .order_by(AppInstall.created_at.desc())
        )
        count_stmt = select(func.count(AppInstall.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        rows = (await self.db.execute(stmt)).scalars().all()
        items = [
            AppInstallOut(
                id=r.id,
                app_id=r.app_id,
                app_name=r.app.name if r.app else "",
                tenant_id=r.tenant_id,
                flow_id=r.flow_id,
                agent_id=r.agent_id,
                kb_id=r.kb_id,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def list_pending_apps(self, params: PageParams) -> PageResult[MarketplaceAppOut]:
        """审核队列：PENDING_REVIEW 状态应用。"""
        filters = [MarketplaceApp.status == MarketplaceAppStatus.PENDING_REVIEW]
        stmt = (
            select(MarketplaceApp)
            .where(*filters)
            .options(selectinload(MarketplaceApp.category))
            .order_by(MarketplaceApp.submitted_at.asc().nulls_last())
        )
        count_stmt = select(func.count(MarketplaceApp.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        installed_ids = await self._installed_app_ids()
        items = [
            self._app_out(
                a,
                installed=a.id in installed_ids,
                category_name=a.category.name if a.category else None,
            )
            for a in apps
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def approve_app(self, app_id: UUID) -> MarketplaceAppOut:
        """审核通过 → PUBLISHED，记录 reviewed_by/at。"""
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PENDING_REVIEW:
            raise BadRequestError("仅待审核应用可通过")
        app.status = MarketplaceAppStatus.PUBLISHED
        app.reviewed_at = datetime.now(timezone.utc)
        app.reviewed_by = self.ctx.user_id
        app.review_note = None
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self._installed_app_ids()
        return self._app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )

    async def reject_app(self, app_id: UUID, *, note: str | None) -> MarketplaceAppOut:
        """驳回 → REJECTED，写入 review_note。"""
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PENDING_REVIEW:
            raise BadRequestError("仅待审核应用可驳回")
        app.status = MarketplaceAppStatus.REJECTED
        app.reviewed_at = datetime.now(timezone.utc)
        app.reviewed_by = self.ctx.user_id
        app.review_note = (note or "").strip() or "未填写驳回原因"
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self._installed_app_ids()
        return self._app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )

    async def list_app_ratings(
        self, app_id: UUID, params: PageParams
    ) -> PageResult[AppRatingOut]:
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise NotFoundError("应用未上架")
        filters = [AppRating.app_id == app_id, not_deleted(AppRating)]
        stmt = (
            select(AppRating)
            .where(*filters)
            .order_by(AppRating.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        count_stmt = select(func.count(AppRating.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        rows = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[AppRatingOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def upsert_rating(self, app_id: UUID, body: AppRatingCreate) -> AppRatingOut:
        """已安装用户每应用一条评分，更新后重算 rating_avg。"""
        app = await self._get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise BadRequestError("仅已上架应用可评分")
        await self._require_installed(app_id)
        existing = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        if existing:
            existing.score = body.score
            existing.comment = body.comment
            rating = existing
        else:
            rating = AppRating(
                app_id=app_id,
                tenant_id=self.ctx.tenant_id,
                user_id=self.ctx.user_id,
                score=body.score,
                comment=body.comment,
            )
            self.db.add(rating)
        await self.db.flush()
        await self._refresh_rating_stats(app_id)
        return AppRatingOut.model_validate(rating)

    async def delete_my_rating(self, app_id: UUID) -> None:
        rating = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        if not rating:
            raise NotFoundError("评分不存在")
        mark_deleted(rating)
        await self.db.flush()
        await self._refresh_rating_stats(app_id)
