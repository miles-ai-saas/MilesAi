"""业务中心服务线演示智能体 seed（按 biz-* 标签匹配 AI 推荐）。"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.agent.agent import Agent, AgentStatus, AgentType
from app.models.meta.tag import EntityTagBinding, TagEntityType, TenantTag
from app.models.platform.tenant import Tenant
from scripts.seed.biz import DEFAULT_SERVICE_LINE_AI

BIZ_AGENT_SPECS: list[dict] = [
    {
        "tag_slug": "biz-brand",
        "tag_name": "业务-品牌",
        "agent_name": "品牌策划助手",
        "description": "协助 VI、品牌手册与比选方案撰写",
        "system_prompt": "你是广告公司的品牌策划顾问，擅长 VI 体系、品牌手册结构与比选分析。回答简洁专业，结合项目阶段给出可执行建议。",
    },
    {
        "tag_slug": "biz-video",
        "tag_name": "业务-影视",
        "agent_name": "影视脚本助手",
        "description": "协助脚本、分镜与宣传片卖点提炼",
        "system_prompt": "你是影视广告项目的脚本顾问，擅长分镜结构、口播文案与拍摄筹备清单。语言清晰，便于客户汇报。",
    },
    {
        "tag_slug": "biz-exhibition",
        "tag_name": "业务-展览",
        "agent_name": "展陈设计助手",
        "description": "协助空间叙事、动线与展陈说明",
        "system_prompt": "你是展览展示项目的展陈顾问，关注参观动线、空间分区与材质工艺说明。",
    },
    {
        "tag_slug": "biz-event",
        "tag_name": "业务-活动",
        "agent_name": "活动策划助手",
        "description": "协助活动方案、流程与预算科目",
        "system_prompt": "你是大型活动策划顾问，擅长流程时间表、预算拆分与应急预案要点。",
    },
    {
        "tag_slug": "biz-training",
        "tag_name": "业务-培训",
        "agent_name": "会务培训助手",
        "description": "协助课程大纲与会务执行分工",
        "system_prompt": "你是会务培训项目顾问，擅长课程大纲、讲师介绍与现场执行分工表。",
    },
    {
        "tag_slug": "biz-signage",
        "tag_name": "业务-标识",
        "agent_name": "导视标识助手",
        "description": "协助导视分级与标识工艺说明",
        "system_prompt": "你是标识导视系统顾问，擅长信息分级、点位清单与工艺材料建议。",
    },
    {
        "tag_slug": "biz-cultural",
        "tag_name": "业务-文创",
        "agent_name": "文创产品助手",
        "description": "协助产品线规划与包装文案",
        "system_prompt": "你是文创产品项目顾问，擅长产品线规划、卖点描述与包装文案。",
    },
    {
        "tag_slug": "biz-print",
        "tag_name": "业务-印刷",
        "agent_name": "宣传品印刷助手",
        "description": "协助装帧工艺与印刷规格说明",
        "system_prompt": "你是宣传品设计印刷顾问，熟悉装帧工艺、纸张规格与色域注意事项。",
    },
]


async def _default_tenant_id(session: AsyncSession) -> UUID | None:
    settings = get_settings()
    return await session.scalar(select(Tenant.id).where(Tenant.name == settings.seed_tenant_name).limit(1))


async def _ensure_tag(session: AsyncSession, tenant_id: UUID, slug: str, name: str) -> TenantTag:
    row = await session.scalar(
        select(TenantTag).where(TenantTag.tenant_id == tenant_id, TenantTag.slug == slug)
    )
    if row:
        return row
    row = TenantTag(tenant_id=tenant_id, slug=slug, name=name)
    session.add(row)
    await session.flush()
    return row


async def _bind_agent_tag(session: AsyncSession, tenant_id: UUID, agent_id: UUID, tag_id: UUID) -> None:
    et = TagEntityType.AGENT.value
    existing = await session.scalar(
        select(EntityTagBinding.id).where(
            EntityTagBinding.tenant_id == tenant_id,
            EntityTagBinding.entity_type == et,
            EntityTagBinding.entity_id == agent_id,
            EntityTagBinding.tag_id == tag_id,
        )
    )
    if existing:
        return
    await session.execute(
        delete(EntityTagBinding).where(
            EntityTagBinding.tenant_id == tenant_id,
            EntityTagBinding.entity_type == et,
            EntityTagBinding.entity_id == agent_id,
        )
    )
    session.add(
        EntityTagBinding(
            tenant_id=tenant_id,
            entity_type=et,
            entity_id=agent_id,
            tag_id=tag_id,
        )
    )


async def seed_biz_service_line_agents(session: AsyncSession) -> None:
    """为默认租户创建带 biz-* 标签的服务线演示智能体。"""
    tenant_id = await _default_tenant_id(session)
    if not tenant_id:
        return

    # 校验 ai_config 中的 tag 与 seed 规格一致
    expected_slugs = {cfg.get("agent_tag") for cfg in DEFAULT_SERVICE_LINE_AI.values() if cfg.get("agent_tag")}

    for spec in BIZ_AGENT_SPECS:
        slug = spec["tag_slug"]
        if slug not in expected_slugs:
            continue

        tag = await _ensure_tag(session, tenant_id, slug, spec["tag_name"])

        agent = await session.scalar(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.name == spec["agent_name"],
            )
        )
        if not agent:
            agent = Agent(
                tenant_id=tenant_id,
                agent_type=AgentType.CUSTOM,
                name=spec["agent_name"],
                description=spec["description"],
                status=AgentStatus.ENABLED,
                system_prompt=spec["system_prompt"],
                config={},
            )
            session.add(agent)
            await session.flush()
        else:
            agent.description = spec["description"]
            agent.system_prompt = spec["system_prompt"]
            agent.status = AgentStatus.ENABLED

        await _bind_agent_tag(session, tenant_id, agent.id, tag.id)

    await session.flush()
