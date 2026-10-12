"""跨会话用户记忆：加载、列表、清空、upsert；支持 scope / 相关性召回。"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_core.logging import get_logger
from miles_core.models.agent import Agent
from miles_core.models.agent.user_memory import AgentUserMemory
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, not_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.agents.repositories.agent import AgentRepository
from miles_portal.tenant.agents.schemas.user_memory import UserMemoryItemOut, UserMemoryListOut

logger = get_logger(__name__)

MEMORY_KINDS = frozenset({"summary", "preference"})
MEMORY_SCOPES = frozenset({"per_agent", "tenant_user"})
RECALL_MODES = frozenset({"all", "relevant"})


def _user_memory_cfg(agent: Agent) -> dict:
    raw = (agent.config or {}).get("user_memory")
    return raw if isinstance(raw, dict) else {}


def user_memory_enabled(agent: Agent) -> bool:
    return bool(_user_memory_cfg(agent).get("enabled"))


def user_memory_max_inject_chars(agent: Agent) -> int:
    cfg = _user_memory_cfg(agent)
    if cfg.get("max_inject_chars") is not None:
        try:
            return max(0, int(cfg["max_inject_chars"]))
        except (TypeError, ValueError):
            pass
    return 2000


def user_memory_scope(agent: Agent) -> str:
    """``per_agent``（默认）或 ``tenant_user``（同租户用户跨智能体画像）。"""
    scope = str(_user_memory_cfg(agent).get("scope") or "per_agent").strip().lower()
    return scope if scope in MEMORY_SCOPES else "per_agent"


def user_memory_recall_mode(agent: Agent) -> str:
    """``all`` 全量注入；``relevant`` 按 query 相关性排序截断。"""
    mode = str(_user_memory_cfg(agent).get("recall_mode") or "all").strip().lower()
    return mode if mode in RECALL_MODES else "all"


def format_long_term_block(
    items: list[AgentUserMemory],
    *,
    max_chars: int = 2000,
    agent_labels: dict[str, str] | None = None,
) -> str:
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
        if agent_labels:
            aname = agent_labels.get(str(row.agent_id))
            if aname:
                label = f"{label}（{aname}）"
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


def _tokenize(text: str) -> set[str]:
    return {t for t in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower()).split() if len(t) > 1}


def _keyword_score(query: str, content: str) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    c = _tokenize(content)
    if not c:
        return 0.0
    return len(q & c) / len(q)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度；维度不一致或零向量返回 0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def rank_memories_for_query(
    rows: list[AgentUserMemory],
    *,
    query: str | None,
    query_embedding: list[float] | None = None,
) -> list[AgentUserMemory]:
    """按向量或关键词相关性降序排列；无 query 时保持原序。"""
    if not query or not rows:
        return list(rows)
    scored: list[tuple[float, AgentUserMemory]] = []
    for row in rows:
        emb = row.content_embedding if isinstance(getattr(row, "content_embedding", None), list) else None
        if query_embedding and emb:
            score = cosine_similarity(query_embedding, [float(x) for x in emb])
        else:
            score = _keyword_score(query, row.content or "")
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


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
        query: str | None = None,
    ) -> tuple[list[AgentUserMemory], str]:
        """返回 (rows, formatted_block)。无用户或未启用时返回空。"""
        if user_id is None or not user_memory_enabled(agent):
            return [], ""
        budget = min(max_chars, user_memory_max_inject_chars(agent))
        scope = user_memory_scope(agent)
        rows, labels = await self._list_rows_for_inject(
            agent_id=agent.id,
            user_id=user_id,
            scope=scope,
        )
        recall = user_memory_recall_mode(agent)
        query_emb: list[float] | None = None
        if recall == "relevant" and query and rows:
            query_emb = await self._embed_text(query)
            rows = rank_memories_for_query(rows, query=query, query_embedding=query_emb)
        return rows, format_long_term_block(rows, max_chars=budget, agent_labels=labels)

    async def _list_rows(self, *, agent_id: UUID, user_id: UUID) -> list[AgentUserMemory]:
        filters = tenant_filters(self.ctx, AgentUserMemory.tenant_id) + [
            AgentUserMemory.agent_id == agent_id,
            AgentUserMemory.user_id == user_id,
        ]
        stmt = select(AgentUserMemory).where(*filters).order_by(AgentUserMemory.kind.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def _list_rows_for_inject(
        self,
        *,
        agent_id: UUID,
        user_id: UUID,
        scope: str,
    ) -> tuple[list[AgentUserMemory], dict[str, str] | None]:
        if scope != "tenant_user":
            return await self._list_rows(agent_id=agent_id, user_id=user_id), None

        filters = tenant_filters(self.ctx, AgentUserMemory.tenant_id) + [
            AgentUserMemory.user_id == user_id,
        ]
        stmt = (
            select(AgentUserMemory)
            .where(*filters)
            .order_by(AgentUserMemory.updated_at.desc())
            .limit(24)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        if not rows:
            return [], None
        agent_ids = {r.agent_id for r in rows}
        name_stmt = select(Agent.id, Agent.name).where(
            Agent.id.in_(agent_ids),
            not_deleted(Agent),
            *tenant_filters(self.ctx, Agent.tenant_id),
        )
        labels = {str(aid): name for aid, name in (await self.db.execute(name_stmt)).all()}
        # 当前智能体的条目优先（同 kind 时）
        rows.sort(key=lambda r: (0 if r.agent_id == agent_id else 1, r.kind))
        return rows, labels

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
        embed: bool = True,
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
        if embed and text:
            emb = await self._embed_text(text)
            if emb is not None:
                row.content_embedding = emb
        await self.db.flush()
        return row

    async def _embed_text(self, text: str) -> list[float] | None:
        """用租户默认 embedding 模型向量化；失败返回 None（不影响主路径）。"""
        try:
            from miles_integrations.embeddings.runtime import build_embeddings
            from miles_portal.tenant.models.services.embedding_resolve import get_default_embedding_model

            model = await get_default_embedding_model(self.db)
            emb = build_embeddings(model)
            vec = emb.embed_query((text or "")[:2000])
            if isinstance(vec, list) and vec:
                return [float(x) for x in vec]
        except Exception:
            logger.debug("user memory embed failed", exc_info=True)
        return None
