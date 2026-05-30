"""智能体对话会话：服务端持久化与查询。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.agent_chat_session import AgentChatMessage, AgentChatSession
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.schemas.chat_sessions import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionDetailOut,
    ChatSessionOut,
    ChatSessionUpdate,
)
from app.common.schema import PageParams, PageResult

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
    if not response.artifacts:
        return None
    return [a.model_dump(mode="json") for a in response.artifacts]


class AgentChatSessionService(BaseService):
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
        count = await self.db.scalar(
            select(func.count()).select_from(AgentChatMessage).where(AgentChatMessage.session_id == row.id)
        )
        return ChatSessionOut(
            id=row.id,
            agent_id=row.agent_id,
            title=row.title,
            message_count=int(count or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_sessions(self, agent_id: UUID, params: PageParams) -> PageResult[ChatSessionOut]:
        await self._ensure_agent(agent_id)
        filters = tenant_filters(self.ctx, AgentChatSession.tenant_id) + [AgentChatSession.agent_id == agent_id]
        total = await self.db.scalar(select(func.count()).select_from(AgentChatSession).where(*filters))
        stmt = (
            select(AgentChatSession)
            .where(*filters)
            .order_by(AgentChatSession.updated_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        rows = list((await self.db.scalars(stmt)).all())
        items = [await self._session_out(row) for row in rows]
        return PageResult(items=items, total=int(total or 0), page=params.page, size=params.size)

    async def create_session(self, agent_id: UUID, body: ChatSessionCreate) -> ChatSessionOut:
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
        now = datetime.now(timezone.utc)
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

    async def get_session(self, agent_id: UUID, session_id: str) -> ChatSessionDetailOut:
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatSession, session_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("会话不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        base = await self._session_out(row)
        msg_rows = list(
            (
                await self.db.scalars(
                    select(AgentChatMessage)
                    .where(AgentChatMessage.session_id == session_id)
                    .order_by(AgentChatMessage.sort_index.asc(), AgentChatMessage.created_at.asc())
                )
            ).all()
        )
        return ChatSessionDetailOut(
            **base.model_dump(),
            messages=[ChatMessageOut.model_validate(m) for m in msg_rows],
        )

    async def update_session(self, agent_id: UUID, session_id: str, body: ChatSessionUpdate) -> ChatSessionOut:
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatSession, session_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("会话不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        row.title = body.title.strip()[:MAX_SESSION_TITLE]
        row.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return await self._session_out(row)

    async def delete_session(self, agent_id: UUID, session_id: str) -> None:
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
        now = datetime.now(timezone.utc)
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
    await AgentChatSessionService(db, ctx).persist_turn(
        agent_id,
        body,
        response=response,
        trace_id=trace_id,
        user_query=user_query,
    )
