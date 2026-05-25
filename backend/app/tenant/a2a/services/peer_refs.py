"""
CUSTOM 智能体 ↔ 外部 A2A Peer 引用（表 ``agt_agent_a2a_peer_refs``）。

字段
----
- ``trigger_keywords``：规则层强制调用（``invoke.evaluate_rule_triggered_peers``）
- ``role_hint``：规划 LLM 选 Peer 时的说明
- 每 Agent 最多 ``MAX_A2A_PEER_REFS``（4）个

对话：``list_agent_a2a_peer_refs`` 仅返回 enabled；与本地 KB 绑定（``agt_kb_bindings``）独立。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.tenant.a2a.models import A2aPeer, A2aPeerStatus, AgentA2aPeerRef
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext
from app.models.agent import Agent, AgentType

MAX_A2A_PEER_REFS = 4


def normalize_peer_refs(
    raw: list[dict] | None,
) -> list[tuple[UUID, str | None, list[str], int, bool]]:
    """解析 API 入参：peer_id、role_hint、trigger_keywords、enabled（最多 4 个）。"""
    if not raw:
        return []
    seen: set[UUID] = set()
    out: list[tuple[UUID, str | None, list[str], int, bool]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            pid = item.get("peer_id")
            hint = item.get("role_hint")
            kw = item.get("trigger_keywords") or []
            enabled = item.get("enabled", True)
        else:
            continue
        if not pid:
            continue
        peer_id = UUID(str(pid))
        if peer_id in seen:
            continue
        seen.add(peer_id)
        keywords: list[str] = []
        if isinstance(kw, list):
            keywords = [str(k).strip() for k in kw if str(k).strip()][:20]
        elif isinstance(kw, str) and kw.strip():
            keywords = [p.strip() for p in kw.replace("，", ",").split(",") if p.strip()][:20]
        rh = (str(hint).strip()[:64] if hint else None) or None
        out.append((peer_id, rh, keywords, i, bool(enabled)))
    if len(out) > MAX_A2A_PEER_REFS:
        raise BadRequestError(f"外部 A2A 引用最多 {MAX_A2A_PEER_REFS} 个")
    return out


async def list_agent_a2a_peer_refs(
    db: AsyncSession,
    agent_id: UUID,
) -> list[AgentA2aPeerRef]:
    """仅 enabled 的引用（对话编排用）。"""
    stmt = (
        select(AgentA2aPeerRef)
        .where(AgentA2aPeerRef.agent_id == agent_id, AgentA2aPeerRef.enabled.is_(True))
        .options(selectinload(AgentA2aPeerRef.peer))
        .order_by(AgentA2aPeerRef.sort_order.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_all_agent_a2a_peer_refs(
    db: AsyncSession,
    agent_id: UUID,
) -> list[AgentA2aPeerRef]:
    """含 disabled 的引用（管理页展示）。"""
    stmt = (
        select(AgentA2aPeerRef)
        .where(AgentA2aPeerRef.agent_id == agent_id)
        .options(selectinload(AgentA2aPeerRef.peer))
        .order_by(AgentA2aPeerRef.sort_order.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


def apply_a2a_config(config: dict | None, *, has_a2a_refs: bool) -> dict:
    """有 A2A 引用时写入默认 invoke 策略到 agent.config。"""
    cfg = dict(config or {})
    if has_a2a_refs:
        cfg.setdefault("a2a_invoke_policy", "rules_then_plan")
        cfg.setdefault("max_a2a_calls_per_turn", 2)
    else:
        for key in ("a2a_invoke_policy", "max_a2a_calls_per_turn", "a2a_peer_count"):
            cfg.pop(key, None)
    return cfg


async def validate_and_sync_agent_a2a_peer_refs(
    db: AsyncSession,
    ctx: TenantContext,
    agent: Agent,
    refs: list[tuple[UUID, str | None, list[str], int, bool]],
) -> None:
    """全量替换自定义智能体的 A2A peer 引用行。"""
    if agent.agent_type != AgentType.CUSTOM:
        raise BadRequestError("仅自定义智能体可引用外部 A2A Agent")

    await db.execute(delete(AgentA2aPeerRef).where(AgentA2aPeerRef.agent_id == agent.id))

    if not refs:
        cfg = apply_a2a_config(agent.config, has_a2a_refs=False)
        agent.config = cfg
        return

    for peer_id, role_hint, keywords, sort_order, enabled in refs:
        peer = await db.get(A2aPeer, peer_id)
        if not peer or is_marked_deleted(peer) or peer.tenant_id != ctx.tenant_id:
            raise NotFoundError("外部 A2A Agent 不存在")
        if peer.status != A2aPeerStatus.ACTIVE:
            raise BadRequestError(
                f"外部 Agent「{peer.name}」未同步 Card（请先同步并确保状态为已连通）"
            )
        db.add(
            AgentA2aPeerRef(
                agent_id=agent.id,
                peer_id=peer_id,
                role_hint=role_hint,
                trigger_keywords=keywords,
                sort_order=sort_order,
                enabled=enabled,
            )
        )
    agent.config = apply_a2a_config(agent.config, has_a2a_refs=bool(refs))
    cfg = dict(agent.config or {})
    cfg["a2a_peer_count"] = len(refs)
    agent.config = cfg
