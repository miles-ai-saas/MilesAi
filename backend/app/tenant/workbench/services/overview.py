from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.prompts.models import PromptTemplate
from app.tenant.workbench.schemas.overview import WorkbenchOverviewOut
from app.core.service import BaseService
from app.core.soft_delete import append_not_deleted, not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.kb import KnowledgeBase
from app.models.model import ModelConfig
from app.models.model_catalog import ModelPublishStatus
from app.models.task import CeleryTaskRecord


class WorkbenchOverviewService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _scalar_count(self, model, *where) -> int:
        return int(
            await self.db.scalar(select(func.count()).select_from(model).where(*where)) or 0
        )

    async def _count_models(self) -> int:
        return await self._scalar_count(
            ModelConfig,
            or_(
                ModelConfig.tenant_id == self.ctx.tenant_id,
                (
                    ModelConfig.tenant_id.is_(None)
                    & (ModelConfig.publish_status == ModelPublishStatus.PUBLISHED.value)
                ),
            ),
            not_deleted(ModelConfig),
        )

    async def overview(self) -> WorkbenchOverviewOut:
        ctx = self.ctx
        out = WorkbenchOverviewOut()

        if ctx.has_permission("agent:read"):
            f = append_not_deleted(tenant_filters(ctx, Agent.tenant_id), Agent)
            out.agents = await self._scalar_count(Agent, *f)

        if ctx.has_permission("kb:read"):
            f = append_not_deleted(tenant_filters(ctx, KnowledgeBase.tenant_id), KnowledgeBase)
            out.kbs = await self._scalar_count(KnowledgeBase, *f)

        if ctx.has_permission("flow:read"):
            f = append_not_deleted(tenant_filters(ctx, Flow.tenant_id), Flow)
            out.flows = await self._scalar_count(Flow, *f)

        if ctx.has_permission("prompt:read"):
            f = append_not_deleted(tenant_filters(ctx, PromptTemplate.tenant_id), PromptTemplate)
            out.prompts = await self._scalar_count(PromptTemplate, *f)

        if ctx.has_permission("model:read"):
            out.models = await self._count_models()

        if ctx.has_permission("task:read"):
            f = tenant_filters(ctx, CeleryTaskRecord.tenant_id)
            out.tasks = await self._scalar_count(CeleryTaskRecord, *f)

        return out
