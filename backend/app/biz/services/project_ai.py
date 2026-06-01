"""项目 AI 上下文：服务线推荐、RAG 策略、结项复盘提示。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.client import ClientRepository
from app.biz.repositories.deliverable import DeliverableRepository
from app.biz.repositories.project import ProjectRepository
from app.biz.repositories.service_line_template import ServiceLineTemplateRepository
from app.biz.services.project_related_cases import ProjectRelatedCasesService
from app.biz.schemas.project_ai import BizProjectAiContextOut, BizServiceLineAiRecommendation
from app.biz.services.meta import SERVICE_LINES
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.tenant import TenantContext, assert_tenant_access
from app.flow_runtime.templates.registry import FLOW_TEMPLATE_REGISTRY
from app.models.agent.agent import Agent, AgentStatus
from app.models.biz.enums import ConfidentialityLevel
from app.models.meta.tag import EntityTagBinding, TagEntityType, TenantTag

_SERVICE_LINE_LABELS = {item.key: item.label for item in SERVICE_LINES}


class ProjectAiContextService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.project_repo = ProjectRepository(db)
        self.client_repo = ClientRepository(db)
        self.deliverable_repo = DeliverableRepository(db)
        self.template_repo = ServiceLineTemplateRepository(db)

    async def get_ai_context(self, project_id: UUID, work_package_id: UUID | None = None) -> BizProjectAiContextOut:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)

        client = await self.client_repo.get_by_id(project.client_id)
        client_name = client.name if client else "—"
        confidentiality = client.confidentiality_level if client else ConfidentialityLevel.NORMAL.value
        rag_enabled = confidentiality != ConfidentialityLevel.RESTRICTED.value

        wps = await self.project_repo.get_work_packages(self.ctx.tenant_id, project_id)
        if work_package_id:
            wps = [wp for wp in wps if wp.id == work_package_id]

        deliverables = await self.deliverable_repo.list_by_project(self.ctx.tenant_id, project_id)
        accepted = sum(1 for d in deliverables if d.status == "accepted")

        recommendations: list[BizServiceLineAiRecommendation] = []
        for wp in wps:
            recommendations.append(await self._build_recommendation(wp.service_line, wp.id, wp.name, wp.stage))

        context_lines = [
            f"项目：{project.name}",
            f"客户：{client_name}",
            f"状态：{project.status}",
        ]
        if project.description:
            context_lines.append(f"描述：{project.description}")
        for wp in wps[:5]:
            context_lines.append(f"工作包「{wp.name}」({ _SERVICE_LINE_LABELS.get(wp.service_line, wp.service_line) }) 阶段：{wp.stage or '—'}")
        if deliverables:
            context_lines.append(f"交付物：共 {len(deliverables)} 项，已验收 {accepted} 项")
        if not rag_enabled:
            context_lines.append("注意：涉密客户项目，请勿引用外部知识库或未授权资料。")
        context_text = "\n".join(context_lines)

        retrospective_available = project.status in ("delivered", "closed") and len(deliverables) > 0
        retrospective_prompt = None
        if retrospective_available:
            names = "、".join(d.name for d in deliverables[:8])
            retrospective_prompt = (
                f"请基于项目「{project.name}」（客户：{client_name}）的交付成果，生成结项复盘报告。"
                f"主要交付物包括：{names}。"
                "请从目标达成、亮点、不足、可复用经验四方面总结，语气专业简洁。"
            )

        related_cases = []
        if rag_enabled:
            related_cases = await ProjectRelatedCasesService(self.db, self.ctx).list_related_cases(project_id)

        return BizProjectAiContextOut(
            project_id=project.id,
            project_name=project.name,
            client_id=project.client_id,
            client_name=client_name,
            confidentiality_level=confidentiality,
            rag_enabled=rag_enabled,
            project_status=project.status,
            context_text=context_text,
            retrospective_available=retrospective_available,
            retrospective_prompt=retrospective_prompt,
            recommendations=recommendations,
            related_cases=related_cases,
        )

    async def _build_recommendation(
        self,
        service_line: str,
        wp_id: UUID,
        wp_name: str,
        stage: str | None,
    ) -> BizServiceLineAiRecommendation:
        template = await self.template_repo.get_active_template(self.ctx.tenant_id, service_line)
        ai_config = (template.ai_config if template and isinstance(template.ai_config, dict) else {}) or {}

        agent_tag = ai_config.get("agent_tag")
        flow_template_id = ai_config.get("flow_template_id")
        chat_hint = ai_config.get("chat_hint")
        quick_prompts = ai_config.get("quick_prompts") if isinstance(ai_config.get("quick_prompts"), list) else []

        agent_id, agent_name = await self._resolve_agent_by_tag(agent_tag) if agent_tag else (None, None)

        flow_label = None
        if flow_template_id:
            spec = next((s for s in FLOW_TEMPLATE_REGISTRY if s.id == flow_template_id), None)
            if spec:
                flow_label = spec.label

        return BizServiceLineAiRecommendation(
            service_line=service_line,
            service_line_label=_SERVICE_LINE_LABELS.get(service_line, service_line),
            work_package_id=wp_id,
            work_package_name=wp_name,
            stage=stage,
            agent_tag=agent_tag,
            recommended_agent_id=agent_id,
            recommended_agent_name=agent_name,
            flow_template_id=flow_template_id,
            flow_template_label=flow_label,
            chat_hint=chat_hint if isinstance(chat_hint, str) else None,
            quick_prompts=[str(p) for p in quick_prompts if p],
        )

    async def _resolve_agent_by_tag(self, tag_slug: str) -> tuple[UUID | None, str | None]:
        tag = await self.db.scalar(
            select(TenantTag).where(
                TenantTag.tenant_id == self.ctx.tenant_id,
                TenantTag.slug == tag_slug,
            )
        )
        if not tag:
            return None, None

        stmt = (
            select(Agent)
            .join(
                EntityTagBinding,
                (EntityTagBinding.entity_id == Agent.id)
                & (EntityTagBinding.entity_type == TagEntityType.AGENT.value)
                & (EntityTagBinding.tag_id == tag.id),
            )
            .where(
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.status == AgentStatus.ENABLED,
            )
            .order_by(Agent.name.asc())
            .limit(1)
        )
        agent = (await self.db.execute(stmt)).scalar_one_or_none()
        if not agent:
            return None, None
        return agent.id, agent.name
