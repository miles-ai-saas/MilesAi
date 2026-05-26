"""租户技能包种子（幂等，可重复执行）。

写入 ORM 并在 ``SKILLS_DATA_ROOT/{tenant_id}/{slug}/`` 落盘 SKILL.md。
命令：``python cli.py seed skills``
依赖：``seed tenant``、``seed categories``。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import not_deleted
from app.models.category import CategoryDomain
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.skill_md import build_skill_md
from app.tenant.skills.storage import write_skill_md

from scripts.seed._helpers import category_id_by_slug, list_tenant_ids

SEED_SKILL_PACKAGES: list[dict] = [
    {
        "slug": "customer_service_playbook",
        "name": "客服应答手册",
        "category_slug": "general",
        "description": "在线客服场景的标准应答结构、转人工边界与合规自检。",
        "tool_names": [],
        "body": """## 适用场景

用户咨询产品、订单、政策；情绪投诉；要求人工。

## 应答结构

1. **确认理解**：一句话复述用户诉求。
2. **解答或引导**：基于已知信息作答；不确定时说明需核实，不编造。
3. **下一步**：给出可执行动作（链接、单号、联系方式）。
4. **转人工**：涉及退款纠纷、法律威胁、媒体曝光时，收集订单号与联系方式并说明将升级。

## 合规

- 不索取密码、验证码、完整银行卡号。
- 不使用绝对化营销用语。
- 对外回复前自检事实性与敏感信息（见提示词模板「合规回复守则」）。""",
    },
    {
        "slug": "rag_qa_assistant",
        "name": "RAG 知识库问答",
        "category_slug": "general",
        "description": "绑定知识库后，指导智能体如何引用检索结果作答。",
        "tool_names": ["knowledge_search"],
        "body": """## 目标

基于知识库检索结果回答用户问题，减少幻觉。

## 步骤

1. 将用户问题整理为检索 query（可保留关键实体与约束）。
2. 调用 **knowledge_search**（或智能体已绑定的 KB 检索能力）获取片段。
3. 仅依据检索片段组织答案；片段不足时明确说明「资料中未找到」，并建议补充文档或联系管理员。
4. 回答中可标注引用来源（文档名/片段摘要），避免大段复制粘贴。

## 输出格式

- 先给结论，再分点展开。
- 存在冲突资料时，指出冲突并给出保守建议。""",
    },
    {
        "slug": "meeting_minutes",
        "name": "会议纪要助手",
        "category_slug": "general",
        "description": "将口语化会议记录整理为结构化纪要。",
        "tool_names": ["get_current_datetime"],
        "body": """## 输入

用户提供会议录音转写、聊天摘录或要点草稿。

## 输出结构

| 区块 | 内容 |
|------|------|
| 基本信息 | 主题、日期（可用 get_current_datetime 补全）、参与人 |
| 结论 | 3–5 条已达成结论 |
| 待办 | 负责人 + 事项 + 截止时间（未知则标 TBD） |
| 风险与遗留 | 未决问题、依赖项 |

## 风格

书面语、去口语填充词；不捏造未在原文出现的决议。""",
    },
    {
        "slug": "code_review_checklist",
        "name": "代码审查清单",
        "category_slug": "general",
        "description": "对 diff 或代码片段做结构化 Review（偏 Web 后端）。",
        "tool_names": ["calculator"],
        "body": """## 审查维度

| 级别 | 检查项 |
|------|--------|
| 严重 | 逻辑错误、注入、鉴权缺失、敏感信息硬编码 |
| 建议 | 命名、重复、边界、错误处理、测试缺口 |
| 优点 | 值得保留的实践（如有） |

## 输出

- 按文件/函数定位问题，并给出简短修改建议。
- 区分「必须修复」与「可选优化」。
- 涉及性能估算时可使用 calculator 辅助，但不替代代码阅读。""",
    },
]


async def _get_or_create_skill(
    session: AsyncSession,
    tenant_id,
    *,
    slug: str,
    name: str,
    description: str | None,
    category_id,
    tool_names: list[str],
    body: str,
) -> SkillPackage:
    row = await session.scalar(
        select(SkillPackage).where(
            SkillPackage.tenant_id == tenant_id,
            SkillPackage.slug == slug,
            not_deleted(SkillPackage),
        )
    )
    if row:
        return row

    row = SkillPackage(
        tenant_id=tenant_id,
        category_id=category_id,
        slug=slug,
        name=name.strip(),
        description=description,
        source_type="manual",
        storage_path=slug,
        tool_names=tool_names,
        config={},
        is_active=True,
    )
    session.add(row)
    await session.flush()
    write_skill_md(
        tenant_id,
        slug,
        build_skill_md(name, description, body),
    )
    await session.refresh(row)
    return row


async def seed_skills_for_tenant(session: AsyncSession, tenant_id) -> int:
    created = 0
    for spec in SEED_SKILL_PACKAGES:
        before = await session.scalar(
            select(SkillPackage.id).where(
                SkillPackage.tenant_id == tenant_id,
                SkillPackage.slug == spec["slug"],
                not_deleted(SkillPackage),
            )
        )
        category_id = await category_id_by_slug(
            session, CategoryDomain.SKILL, spec.get("category_slug")
        )
        await _get_or_create_skill(
            session,
            tenant_id,
            slug=spec["slug"],
            name=spec["name"],
            description=spec.get("description"),
            category_id=category_id,
            tool_names=list(spec.get("tool_names") or []),
            body=spec.get("body", "").strip(),
        )
        if before is None:
            created += 1
    await session.flush()
    return created


async def seed_skills(session: AsyncSession) -> None:
    total_created = 0
    for tenant_id in await list_tenant_ids(session):
        total_created += await seed_skills_for_tenant(session, tenant_id)
    print(f">>> skills seed: created {total_created} skill package(s) across tenants")
