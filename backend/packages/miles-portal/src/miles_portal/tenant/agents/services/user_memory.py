"""跨会话用户记忆：加载、列表、清空、upsert。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_core.models.agent import Agent
from miles_core.models.agent.user_memory import AgentUserMemory
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.agents.repositories.agent import AgentRepository
from miles_portal.tenant.agents.schemas.user_memory import UserMemoryItemOut, UserMemoryListOut

MEMORY_KINDS = frozenset({"summary", "preference"})


def user_memory_enabled(agent: Agent) -> bool:
    cfg = (agent.config or {}).get("user_memory")
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("enabled"))


def user_memory_max_inject_chars(agent: Agent) -> int:
    cfg = (agent.config or {}).get("user_memory")
    if isinstance(cfg, dict) and cfg.get("max_inject_chars") is not None:
        try:
            return max(0, int(cfg["max_inject_chars"]))
        except (TypeError, ValueError):
            pass
    return 2000


def format_long_term_block(items: list[AgentUserMemory], *, max_chars: int = 2000) -> str:
    """拼进 system_prompt 的长期记忆块；空则返回空串。"""
    if not items or max_chars <= 0:
        return ""
    kind_label = {"preference": "偏好", "summary": "摘要"}
    lines: list[str] = []
    used = 0
    for row in items:
        content = (row.content or "").strip()
        if not content:
            continue
        label = kind_label.get(row.kind, row.kind)
        line = f"- {label}：{content}"
        if used + len(line) + 1 > max_chars:
            remain = max_chars - used - 1
            if remain > 20:
                lines.append(line[:remain] + "…")
            break
        lines.append(line)
        used += len(line) + 1
    if not lines:
        return ""
    return "\n\n【关于该用户的长期记忆】\n" + "\n".join(lines)


class UserMemoryService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._repo = AgentRepository(db)

    async def _ensure_agent(self, agent_id: UUID) -> Agent:
        agent = await self._repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)
        return agent

    async def load_for_inject(
        self,
        *,
        agent: Agent,
        user_id: UUID | None,
        max_chars: int = 2000,
    ) -> tuple[list[AgentUserMemory], str]:
        """返回 (rows, formatted_block)。无用户或未启用时返回空。"""
        if user_id is None or not user_memory_enabled(agent):
            return [], ""
        budget = min(max_chars, user_memory_max_inject_chars(agent))
        rows = await self._list_rows(agent_id=agent.id, user_id=user_id)
        return rows, format_long_term_block(rows, max_chars=budget)

    async def _list_rows(self, *, agent_id: UUID, user_id: UUID) -> list[AgentUserMemory]:
        filters = tenant_filters(self.ctx, AgentUserMemory.tenant_id) + [
            AgentUserMemory.agent_id == agent_id,
            AgentUserMemory.user_id == user_id,
        ]
        stmt = select(AgentUserMemory).where(*filters).order_by(AgentUserMemory.kind.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_mine(self, agent_id: UUID) -> UserMemoryListOut:
        await self._ensure_agent(agent_id)
        rows = await self._list_rows(agent_id=agent_id, user_id=self.ctx.user_id)
        return UserMemoryListOut(items=[UserMemoryItemOut.model_validate(r) for r in rows])

    async def get_mine(self, agent_id: UUID, kind: str) -> UserMemoryItemOut:
        await self._ensure_agent(agent_id)
        if kind not in MEMORY_KINDS:
            raise NotFoundError("记忆类型不存在")
        filters = tenant_filters(self.ctx, AgentUserMemory.tenant_id) + [
            AgentUserMemory.agent_id == agent_id,
            AgentUserMemory.user_id == self.ctx.user_id,
            AgentUserMemory.kind == kind,
        ]
        row = (await self.db.execute(select(AgentUserMemory).where(*filters))).scalar_one_or_none()
        if not row:
            raise NotFoundError("暂无该类型记忆")
        return UserMemoryItemOut.model_validate(row)

    async def clear_mine(self, agent_id: UUID) -> int:
        await self._ensure_agent(agent_id)
        filters = tenant_filters(self.ctx, AgentUserMemory.tenant_id) + [
            AgentUserMemory.agent_id == agent_id,
            AgentUserMemory.user_id == self.ctx.user_id,
        ]
        result = await self.db.execute(delete(AgentUserMemory).where(*filters))
        return int(result.rowcount or 0)

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
        kind: str,
        content: str,
        source_trace_id: str | None = None,
    ) -> AgentUserMemory:
        if kind not in MEMORY_KINDS:
            raise ValueError(f"unsupported kind: {kind}")
        text = (content or "").strip()
        filters = [
            AgentUserMemory.tenant_id == tenant_id,
            AgentUserMemory.user_id == user_id,
            AgentUserMemory.agent_id == agent_id,
            AgentUserMemory.kind == kind,
        ]
        row = (await self.db.execute(select(AgentUserMemory).where(*filters))).scalar_one_or_none()
        if row is None:
            if not text:
                return AgentUserMemory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    kind=kind,
                    content="",
                )
            row = AgentUserMemory(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                kind=kind,
                content=text,
                source_trace_id=source_trace_id,
            )
            self.db.add(row)
        else:
            if not text:
                await self.db.delete(row)
                return row
            row.content = text
            row.source_trace_id = source_trace_id
        await self.db.flush()
        return row
