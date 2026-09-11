"""
A2A 宿主智能体 ↔ 外部 Peer（表 ``agt_a2a_peer_bindings``）。

``AgentType.A2A`` 专用：不绑本地 KB/流程，``chat`` 走 ``run_a2a_host_chat``。
``apply_host_config`` 注入 ``runtime_mode=autonomous``、``planner=a2a_orchestrator``，
与 CUSTOM 智能体的 LangGraph RAG（``should_use_langgraph_rag``）互斥。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_portal.tenant.agents.constants import AgentPlanner, AgentRuntimeMode
from miles_portal.tenant.a2a.models import A2aInvokePolicy, A2aPeer, A2aPeerBinding, A2aPeerStatus
from miles_portal.tenant.a2a.services.peer_refs import normalize_peer_refs
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext
from miles_core.models.agent import Agent, AgentType

MAX_HOST_PEERS = 8
MIN_HOST_PEERS = 1


def apply_host_config(config: dict | None, *, has_peers: bool) -> dict:
    """A2A 宿主 config：runtime_mode=autonomous、planner=a2a_orchestrator。"""
    cfg = dict(config or {})
    if has_peers:
        cfg["runtime_mode"] = AgentRuntimeMode.AUTONOMOUS.value
        cfg["planner"] = AgentPlanner.A2A_ORCHESTRATOR.value
        cfg.setdefault("a2a_invoke_policy", A2aInvokePolicy.RULES_THEN_PLAN.value)
        cfg.setdefault("max_a2a_calls_per_turn", 3)
    else:
        for key in (
            "runtime_mode",
            "planner",
            "a2a_invoke_policy",
            "max_a2a_calls_per_turn",
            "a2a_host_peer_count",
        ):
            cfg.pop(key, None)
    return cfg


async def list_host_peer_bindings(
    db: AsyncSession,
    parent_agent_id: UUID,
    *,
    enabled_only: bool = False,
) -> list[A2aPeerBinding]:
    """查询 A2A 宿主绑定的外部 peer 列表。"""
    stmt = (
        select(A2aPeerBinding)
        .where(A2aPeerBinding.parent_agent_id == parent_agent_id)
        .options(selectinload(A2aPeerBinding.peer))
        .order_by(A2aPeerBinding.sort_order.asc())
    )
    if enabled_only:
        stmt = stmt.where(A2aPeerBinding.enabled.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def validate_and_sync_host_peer_bindings(
    db: AsyncSession,
    ctx: TenantContext,
    host: Agent,
    refs: list[tuple[UUID, str | None, list[str], int, bool]],
) -> None:
    """全量替换宿主绑定；peer 须为 ACTIVE。"""
    if host.agent_type != AgentType.A2A:
        raise BadRequestError("仅 A2A 互联宿主可绑定外部 Peer")

    if len(refs) < MIN_HOST_PEERS:
        raise BadRequestError(f"A2A 宿主至少绑定 {MIN_HOST_PEERS} 个已连通的外部 Agent")

    for peer_id, _role_hint, _keywords, _sort_order, _enabled in refs:
        peer = await db.get(A2aPeer, peer_id)
        if not peer or is_marked_deleted(peer) or peer.tenant_id != ctx.tenant_id:
            raise NotFoundError("外部 A2A Agent 不存在")
        if peer.status != A2aPeerStatus.ACTIVE:
            raise BadRequestError(f"外部 Agent「{peer.name}」须先同步 Agent Card（状态已连通）")

    await db.execute(delete(A2aPeerBinding).where(A2aPeerBinding.parent_agent_id == host.id))

    for peer_id, role_hint, keywords, sort_order, enabled in refs:
        db.add(
            A2aPeerBinding(
                parent_agent_id=host.id,
                peer_id=peer_id,
                role_hint=role_hint,
                trigger_keywords=keywords,
                sort_order=sort_order,
                enabled=enabled,
            )
        )

    cfg = apply_host_config(host.config, has_peers=True)
    cfg["a2a_host_peer_count"] = len(refs)
    host.config = cfg


def normalize_host_peers(raw: list[dict] | None) -> list[tuple[UUID, str | None, list[str], int, bool]]:
    """宿主绑定解析，上限 MAX_HOST_PEERS=8。"""
    out = normalize_peer_refs(raw)
    if len(out) > MAX_HOST_PEERS:
        raise BadRequestError(f"A2A 宿主最多绑定 {MAX_HOST_PEERS} 个外部 Agent")
    return out
