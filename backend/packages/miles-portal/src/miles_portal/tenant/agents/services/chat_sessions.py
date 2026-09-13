"""智能体对话会话：服务端持久化与查询。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.agent.chat_session import AgentChatMessage, AgentChatSession
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.agents.repositories.agent import AgentRepository
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.schemas.chat_sessions import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionDetailOut,
    ChatSessionOut,
    ChatSessionUpdate,
)
from miles_portal.tenant.agents.services.chat_artifact_sync import hydrate_chat_messages_artifacts

MAX_SESSION_TITLE = 128
TITLE_PREVIEW_LEN = 28


def _derive_title(current: str, user_query: str) -> str:
    if current != "新对话" or not user_query.strip():
        return current
    text = user_query.strip()
    title = text[:TITLE_PREVIEW_LEN] + ("…" if len(text) > TITLE_PREVIEW_LEN else "")
    return title[:MAX_SESSION_TITLE]


def _media_payload(body: ChatRequest) -> list[dict] | None:
    if not body.media:
        return None
    return [{"attachment_id": str(m.attachment_id), "detail": m.detail} for m in body.media]


def _artifacts_payload(response: ChatResponse) -> list[dict] | None:
    """持久化 artifacts；若仅有 generative_jobs 占位也要写入 job_id，便于任务完成后回写。"""
    arts: list[dict] = []
    seen: set[str] = set()
    for a in response.artifacts or []:
        dumped = a.model_dump(mode="json")
        arts.append(dumped)
        jid = dumped.get("job_id")
        if jid:
            seen.add(str(jid))
    for job in response.generative_jobs or []:
        if isinstance(job, dict):
            jid = str(job.get("id") or "")
            kind = job.get("kind") or "image"
            status = job.get("status") or "pending"
        else:
            jid = str(getattr(job, "id", "") or "")
            kind = getattr(job, "kind", None) or "image"
            status = getattr(job, "status", None) or "pending"
        if not jid or jid in seen:
            continue
        seen.add(jid)
        arts.append(
            {
                "kind": "image" if kind == "image" else "video",
                "job_id": jid,
                "status": status if status in ("pending", "running", "success", "failed", "cancelled") else "pending",
            }
        )
    return arts or None


class AgentChatSessionService(BaseService):
    """对话会话与消息的服务端持久化及查询服务。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._agent_repo = AgentRepository(db)

    async def _ensure_agent(self, agent_id: UUID) -> None:
        agent = await self._agent_repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

    async def _next_sort_index(self, session_id: str) -> int:
        current = await self.db.scalar(
            select(func.coalesce(func.max(AgentChatMessage.sort_index), -1)).where(
                AgentChatMessage.session_id == session_id,
            )
        )
        return int(current or -1) + 1

    async def _session_out(self, row: AgentChatSession) -> ChatSessionOut:
        count = await self.db.scalar(select(func.count()).select_from(AgentChatMessage).where(AgentChatMessage.session_id == row.id))
        return ChatSessionOut(
            id=row.id,
            agent_id=row.agent_id,
            title=row.title,
            message_count=int(count or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_sessions(self, agent_id: UUID, params: PageParams) -> PageResult[ChatSessionOut]:
        """分页列出智能体的会话，按更新时间倒序。"""
        await self._ensure_agent(agent_id)
        filters = tenant_filters(self.ctx, AgentChatSession.tenant_id) + [AgentChatSession.agent_id == agent_id]
        total = await self.db.scalar(select(func.count()).select_from(AgentChatSession).where(*filters))
        stmt = select(AgentChatSession).where(*filters).order_by(AgentChatSession.updated_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        rows = list((await self.db.scalars(stmt)).all())
        items = [await self._session_out(row) for row in rows]
        return PageResult(items=items, total=int(total or 0), page=params.page, size=params.size)

    async def create_session(self, agent_id: UUID, body: ChatSessionCreate) -> ChatSessionOut:
        """创建会话；同 ID 已存在且属于同一智能体时直接复用，否则报错。"""
        await self._ensure_agent(agent_id)
        session_id = (body.id or str(uuid4())).strip()
        if not session_id:
            raise BadRequestError("会话 ID 无效")
        existing = await self.db.get(AgentChatSession, session_id)
        if existing:
            assert_tenant_access(self.ctx, existing.tenant_id)
            if existing.agent_id != agent_id:
                raise BadRequestError("会话 ID 已被其他智能体使用")
            return await self._session_out(existing)
        now = datetime.now(UTC)
        row = AgentChatSession(
            id=session_id,
            tenant_id=self.ctx.tenant_id,
            agent_id=agent_id,
            title=body.title[:MAX_SESSION_TITLE] or "新对话",
            created_by=self.ctx.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()
        return await self._session_out(row)

    async def get_session(
        self,
        agent_id: UUID,
        session_id: str,
        *,
        before_sort_index: int | None = None,
        limit: int = 10,
    ) -> ChatSessionDetailOut:
        """获取会话详情，默认返回最新 N 条消息；传 before_sort_index 可向前翻页。"""
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatSession, session_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("会话不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        base = await self._session_out(row)

        stmt = select(AgentChatMessage).where(
            AgentChatMessage.session_id == session_id,
        )
        if before_sort_index is not None:
            stmt = stmt.where(AgentChatMessage.sort_index < before_sort_index)
        stmt = stmt.order_by(AgentChatMessage.sort_index.desc()).limit(limit + 1)

        rows = list((await self.db.scalars(stmt)).all())
        has_more = len(rows) > limit
        msg_rows = rows[:limit]
        # 数据库返回的是 sort_index desc，翻转回 asc 顺序
        msg_rows.reverse()

        await hydrate_chat_messages_artifacts(self.db, msg_rows)

        return ChatSessionDetailOut(
            **base.model_dump(),
            messages=[ChatMessageOut.model_validate(m) for m in msg_rows],
            has_more=has_more,
        )

    async def update_session(self, agent_id: UUID, session_id: str, body: ChatSessionUpdate) -> ChatSessionOut:
        """更新会话标题并刷新更新时间。"""
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatSession, session_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("会话不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        row.title = body.title.strip()[:MAX_SESSION_TITLE]
        row.updated_at = datetime.now(UTC)
        await self.db.flush()
        return await self._session_out(row)

    async def delete_session(self, agent_id: UUID, session_id: str) -> None:
        """物理删除会话及其全部消息。"""
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatSession, session_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("会话不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await self.db.execute(delete(AgentChatMessage).where(AgentChatMessage.session_id == session_id))
        await self.db.delete(row)
        await self.db.flush()

    async def persist_turn(
        self,
        agent_id: UUID,
        body: ChatRequest,
        *,
        response: ChatResponse | None,
        trace_id: str | None,
        user_query: str,
    ) -> None:
        """chat 回合结束后写入会话与消息（与本地 chat-sessions 结构对齐）。"""
        conversation_id = (body.conversation_id or "").strip()
        if not conversation_id:
            return

        row = await self.db.get(AgentChatSession, conversation_id)
        now = datetime.now(UTC)
        if not row:
            row = AgentChatSession(
                id=conversation_id,
                tenant_id=self.ctx.tenant_id,
                agent_id=agent_id,
                title="新对话",
                created_by=self.ctx.user_id,
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
            await self.db.flush()
        elif row.agent_id != agent_id or row.tenant_id != self.ctx.tenant_id:
            return

        row.title = _derive_title(row.title, user_query)
        row.updated_at = now

        sort = await self._next_sort_index(conversation_id)
        media = _media_payload(body)
        self.db.add(
            AgentChatMessage(
                session_id=conversation_id,
                tenant_id=self.ctx.tenant_id,
                agent_id=agent_id,
                role="user",
                content=user_query,
                media=media,
                sort_index=sort,
            )
        )

        if response is not None:
            steps = response.steps or None
            self.db.add(
                AgentChatMessage(
                    session_id=conversation_id,
                    tenant_id=self.ctx.tenant_id,
                    agent_id=agent_id,
                    role="assistant",
                    content=response.answer,
                    artifacts=_artifacts_payload(response),
                    steps=steps if steps else None,
                    trace_id=trace_id,
                    sort_index=sort + 1,
                )
            )

        await self.db.flush()


async def persist_chat_turn(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    body: ChatRequest,
    *,
    response: ChatResponse | None,
    trace_id: str | None,
    user_query: str,
) -> None:
    """写入一轮对话（用户消息 + 可选助手消息）的便捷入口。"""
    await AgentChatSessionService(db, ctx).persist_turn(
        agent_id,
        body,
        response=response,
        trace_id=trace_id,
        user_query=user_query,
    )
