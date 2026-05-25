"""
子智能体绑定（表 ``agt_sub_agent_bindings``）：校验、同步、环检测。

创建/更新 Agent 时
------------------
- ``validate_and_sync_sub_agents``：最多 8 个、禁止自引用与 DAG 成环
- ``apply_planner_config``：写入 ``runtime_mode=autonomous``、``planner=deepagents``

对话
----
``AgentService.chat`` 有绑定时走 ``integrations.deepagents.orchestrator``，
**不**与父 Agent 的 ``published_flow_id`` / 单 Agent ``_rag_chat`` 同轮并存（先命中子 Agent 分支）。

子智能体 ``chat_as_child`` 仍可绑定 ``knowledge_bases``，检索链路与父 Agent RAG 相同。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext
from app.models.agent import Agent, AgentSubAgentBinding, AgentType

MAX_SUB_AGENTS = 8

ROLE_HINTS = frozenset({"retrieval", "ocr", "summary", "compliance", "custom"})


def apply_planner_config(config: dict | None, *, has_sub_agents: bool) -> dict:
    """有子智能体时写入 planner=deepagents 等默认项。"""
    cfg = dict(config or {})
    if has_sub_agents:
        cfg["runtime_mode"] = "autonomous"
        cfg["planner"] = "deepagents"
        cfg.setdefault("max_plan_iterations", 12)
        cfg.setdefault("max_subagent_calls", 20)
        cfg.setdefault("subagent_parallel", False)
    else:
        for key in ("planner", "max_plan_iterations", "max_subagent_calls", "subagent_parallel"):
            cfg.pop(key, None)
    return cfg


def normalize_bindings(
    raw: list[dict] | None,
) -> list[tuple[UUID, str | None, int]]:
    """解析 child_agent_id + role_hint（最多 8 个）。"""
    if not raw:
        return []
    seen: set[UUID] = set()
    out: list[tuple[UUID, str | None, int]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            cid = item.get("child_agent_id")
            hint = item.get("role_hint")
        else:
            cid = item
            hint = None
        if not cid:
            continue
        child_id = UUID(str(cid))
        if child_id in seen:
            continue
        seen.add(child_id)
        rh = (str(hint).strip()[:64] if hint else None) or None
        if rh and rh not in ROLE_HINTS:
            rh = "custom"
        out.append((child_id, rh, i))
    if len(out) > MAX_SUB_AGENTS:
        raise BadRequestError(f"子智能体最多绑定 {MAX_SUB_AGENTS} 个")
    return out


async def _load_agent(db: AsyncSession, agent_id: UUID, tenant_id: UUID) -> Agent:
    agent = await db.get(Agent, agent_id)
    if not agent or is_marked_deleted(agent) or agent.tenant_id != tenant_id:
        raise NotFoundError("智能体不存在")
    return agent


async def _would_create_cycle(
    db: AsyncSession,
    parent_id: UUID,
    child_ids: list[UUID],
) -> bool:
    """若添加 parent→child 边后存在环则返回 True。"""
    if not child_ids:
        return False
    stmt = select(
        AgentSubAgentBinding.parent_agent_id,
        AgentSubAgentBinding.child_agent_id,
    )
    edges = (await db.execute(stmt)).all()
    adj: dict[UUID, list[UUID]] = {}
    for p, c in edges:
        adj.setdefault(p, []).append(c)
    for cid in child_ids:
        adj.setdefault(parent_id, []).append(cid)

    visited: set[UUID] = set()
    stack: set[UUID] = set()

    def dfs(node: UUID) -> bool:
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for nxt in adj.get(node, []):
            if dfs(nxt):
                return True
        stack.remove(node)
        return False

    for start in adj:
        if dfs(start):
            return True
    return False


def validate_agent_type_constraints(
    *,
    agent_type: AgentType,
    kb_ids: list | None = None,
    published_flow_id: UUID | None = None,
    sub_agents: list | None = None,
    a2a_peers: list | None = None,
    model_config_id: UUID | None = None,
    is_create: bool = False,
) -> None:
    """A2A 宿主与内部协同、KB/流程互斥。"""
    if agent_type != AgentType.A2A:
        return
    if sub_agents:
        raise BadRequestError("A2A 互联宿主不支持绑定平台内子智能体")
    if kb_ids:
        raise BadRequestError("A2A 互联宿主不支持绑定知识库")
    if published_flow_id:
        raise BadRequestError("A2A 互联宿主不支持绑定可视化流程")
    if is_create and not model_config_id:
        raise BadRequestError("A2A 互联宿主须选择编排模型")
    if is_create and not a2a_peers:
        raise BadRequestError("A2A 互联宿主须至少绑定 1 个已连通的外部 Agent")


async def validate_and_sync_sub_agents(
    db: AsyncSession,
    ctx: TenantContext,
    parent: Agent,
    bindings: list[tuple[UUID, str | None, int]],
) -> None:
    """全量替换子智能体绑定；禁止环与二层嵌套。"""
    if parent.agent_type == AgentType.A2A:
        raise BadRequestError("A2A 互联智能体不支持平台内子智能体绑定")
    if not bindings:
        await db.execute(
            delete(AgentSubAgentBinding).where(
                AgentSubAgentBinding.parent_agent_id == parent.id
            )
        )
        return

    child_ids = [b[0] for b in bindings]
    if parent.id in child_ids:
        raise BadRequestError("不能将智能体绑定为自身的子智能体")

    if await _would_create_cycle(db, parent.id, child_ids):
        raise BadRequestError("子智能体绑定存在循环依赖")

    for cid in child_ids:
        child = await _load_agent(db, cid, ctx.tenant_id)
        if child.agent_type != AgentType.CUSTOM:
            raise BadRequestError(
                f"「{child.name}」为 A2A 互联智能体，不能作为内部协同子节点"
            )
        if child.status.value != "enabled":
            raise BadRequestError(f"子智能体「{child.name}」未启用")
        child_as_parent = await db.scalar(
            select(AgentSubAgentBinding.child_agent_id)
            .where(AgentSubAgentBinding.parent_agent_id == cid)
            .limit(1)
        )
        if child_as_parent:
            raise BadRequestError(
                f"子智能体「{child.name}」已绑定其他子智能体，仅支持一层委派"
            )

    await db.execute(
        delete(AgentSubAgentBinding).where(AgentSubAgentBinding.parent_agent_id == parent.id)
    )
    for child_id, role_hint, sort_order in bindings:
        db.add(
            AgentSubAgentBinding(
                parent_agent_id=parent.id,
                child_agent_id=child_id,
                role_hint=role_hint,
                sort_order=sort_order,
            )
        )


async def list_sub_agent_bindings(
    db: AsyncSession,
    parent_id: UUID,
) -> list[AgentSubAgentBinding]:
    """加载父智能体的子绑定（含 child_agent）。"""
    stmt = (
        select(AgentSubAgentBinding)
        .where(AgentSubAgentBinding.parent_agent_id == parent_id)
        .options(selectinload(AgentSubAgentBinding.child_agent))
        .order_by(AgentSubAgentBinding.sort_order.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def unlink_sub_agent_bindings(
    db: AsyncSession,
    *,
    parent_agent_id: UUID | None = None,
    child_agent_id: UUID | None = None,
) -> None:
    if parent_agent_id is None and child_agent_id is None:
        return
    stmt = delete(AgentSubAgentBinding)
    if parent_agent_id is not None:
        stmt = stmt.where(AgentSubAgentBinding.parent_agent_id == parent_agent_id)
    if child_agent_id is not None:
        stmt = stmt.where(AgentSubAgentBinding.child_agent_id == child_agent_id)
    await db.execute(stmt)
