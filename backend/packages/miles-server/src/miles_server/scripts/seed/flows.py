"""租户流程画布种子（幂等，可重复执行）。

命令：`milesai seed flows`
依赖：先执行 `seed tenant`（需存在租户）。

每个租户写入 2 条已发布示例流程（RAG + 简单对话）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.flow_runtime.templates.registry import load_flow_template_graph
from miles_core.models.flow import Flow, FlowStatus, FlowVersion
from miles_core.models.platform.tenant import Tenant
from miles_core.soft_delete import is_marked_deleted, not_deleted

SEED_FLOW_SPECS: list[dict] = [
    {
        "name": "【示例】RAG 问答",
        "template_id": "rag",
        "description": "检索 → 提示词 → 大模型，适合绑定知识库后使用。",
        "publish": True,
    },
    {
        "name": "【示例】简单对话",
        "template_id": "simple_llm",
        "description": "用户输入直连大模型，无知识库。",
        "publish": True,
    },
]


async def _get_or_create_flow(
    session: AsyncSession,
    tenant_id,
    *,
    name: str,
    description: str | None,
    template_id: str,
    publish: bool,
) -> Flow:
    # 1. 优先复用未删除的已有 flow
    row = await session.scalar(
        select(Flow).where(
            Flow.tenant_id == tenant_id,
            Flow.name == name,
            not_deleted(Flow),
        )
    )
    if row:
        return row

    # 2. 若已存在同名但被软删的 flow → 恢复它（保持 UUID 不变，避免前端缓存 ID 404）
    deleted_row = await session.scalar(
        select(Flow).where(
            Flow.tenant_id == tenant_id,
            Flow.name == name,
        )
    )
    if deleted_row and is_marked_deleted(deleted_row):
        deleted_row.deleted_at = None
        deleted_row.status = FlowStatus.PUBLISHED if publish else FlowStatus.DRAFT
        await session.flush()
        return deleted_row

    # 3. 全新创建
    graph = load_flow_template_graph(template_id)
    flow = Flow(
        tenant_id=tenant_id,
        name=name,
        description=description,
        status=FlowStatus.PUBLISHED if publish else FlowStatus.DRAFT,
        current_version=1,
    )
    session.add(flow)
    await session.flush()

    version = FlowVersion(
        flow_id=flow.id,
        version=1,
        graph_json=graph,
        editor_id=None,
        remark=f"种子模板: {template_id}",
    )
    session.add(version)
    await session.flush()
    await session.refresh(flow)
    return flow


async def seed_flows_for_tenant(session: AsyncSession, tenant_id) -> None:
    for spec in SEED_FLOW_SPECS:
        await _get_or_create_flow(
            session,
            tenant_id,
            name=spec["name"],
            description=spec.get("description"),
            template_id=spec["template_id"],
            publish=bool(spec.get("publish", True)),
        )
    await session.flush()


async def seed_flows(session: AsyncSession) -> None:
    tenant_ids = (await session.execute(select(Tenant.id))).scalars().all()
    if not tenant_ids:
        return
    for tid in tenant_ids:
        await seed_flows_for_tenant(session, tid)
