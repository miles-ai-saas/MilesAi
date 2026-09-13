"""工作台首页聚合统计（KB/智能体/流程/任务等计数）。"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.agent import Agent
from miles_core.models.flow import Flow
from miles_core.models.kb import KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus
from miles_core.models.task.task_record import CeleryTaskRecord
from miles_core.service import BaseService
from miles_core.soft_delete import append_not_deleted, not_deleted
from miles_core.tenant import TenantContext, tenant_filters
from miles_portal.tenant.prompts.models import PromptTemplate
from miles_portal.tenant.workbench.schemas.overview import WorkbenchOverviewOut


class WorkbenchOverviewService(BaseService):
    """按当前用户权限仅统计其有读权限的模块数量。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _scalar_count(self, model, *where) -> int:
        """单表 count 查询。"""
        return int(await self.db.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    async def _count_models(self) -> int:
        return await self._scalar_count(
            ModelConfig,
            or_(
                ModelConfig.tenant_id == self.ctx.tenant_id,
                (ModelConfig.tenant_id.is_(None) & (ModelConfig.publish_status == ModelPublishStatus.PUBLISHED.value)),
            ),
            not_deleted(ModelConfig),
        )

    async def overview(self) -> WorkbenchOverviewOut:
        """首页卡片数字；无权限的字段保持默认 0。"""
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
