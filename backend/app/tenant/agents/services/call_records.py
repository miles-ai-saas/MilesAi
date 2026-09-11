"""智能体对话调用记录：写入辅助与列表查询。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.trace import get_trace_id
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.agent.chat_call import AgentChatCall
from app.models.platform.user import User
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.schemas.call_records import AgentCallRecordDetailOut, AgentCallRecordOut
from app.tenant.agents.services.chat_sessions import persist_chat_turn
from app.common.schema import PageParams, PageResult
from app.tenant.hooks.models import HookExecutionLog
from app.tenant.hooks.schemas.execution import HookExecutionLogOut
from app.tenant.models.services.usage import get_chat_usage_totals
from app.tenant.tools.models import ToolInvocationLog
from app.tenant.tools.schemas.tools import ToolInvocationLogOut

PREVIEW_MAX_LEN = 200
RELATED_LOG_LIMIT = 20
CORRELATION_PAD_BEFORE_SEC = 5
CORRELATION_PAD_AFTER_SEC = 30
_TOOL_STEP_TYPES = frozenset(
    {
        "tool",
        "tool_call",
        "tool_invoke",
        "generate_image",
        "generate_video",
        "knowledge_search",
    },
)


def preview_text(text: str, *, max_len: int = PREVIEW_MAX_LEN) -> str:
    """截断文本用于列表预览，超长时追加省略号。"""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len]}…"


def build_steps_summary(steps: list[dict] | None) -> list[dict]:
    """抽取步骤的 type/label 生成精简摘要（最多 50 条）。"""
    out: list[dict] = []
    for step in steps or []:
        step_type = str(step.get("type") or "step")
        label = step.get("label") or step.get("name") or step_type
        out.append({"type": step_type, "label": str(label)[:128]})
        if len(out) >= 50:
            break
    return out


def count_tool_calls(steps: list[dict] | None) -> int:
    """统计步骤中属于工具调用类型的数量。"""
    return sum(1 for step in steps or [] if str(step.get("type") or "") in _TOOL_STEP_TYPES)


def is_compliance_block(exc: Exception) -> bool:
    """判断异常是否为合规敏感词拦截（据此将状态记为 blocked）。"""
    return isinstance(exc, BadRequestError) and "敏感词" in exc.message


def correlation_window(created_at: datetime, latency_ms: int) -> tuple[datetime, datetime]:
    """调用记录关联工具日志的时间窗（created_at 前后缓冲）。"""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    start = created_at - timedelta(seconds=CORRELATION_PAD_BEFORE_SEC)
    end = created_at + timedelta(milliseconds=max(latency_ms, 0)) + timedelta(seconds=CORRELATION_PAD_AFTER_SEC)
    return start, end


class ChatCallRecorder:
    """单轮 chat 调用记录写入器（与 chat 同事务 flush）。"""

    def __init__(
        self,
        db: AsyncSession,
        ctx: TenantContext,
        *,
        agent_id: UUID,
        body: ChatRequest,
        user_query: str,
        media_count: int = 0,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.agent_id = agent_id
        self.body = body
        self.user_query = user_query
        self.conversation_id = body.conversation_id
        self.query_preview = preview_text(user_query)
        self.media_count = media_count
        self._started = time.perf_counter()
        self._route = "unknown"
        self._written = False

    def set_route(self, route: str) -> None:
        """记录本轮实际命中的路由标识。"""
        self._route = route

    @property
    def route(self) -> str:
        """返回本轮实际命中的路由标识。"""
        return self._route

    def _latency_ms(self) -> int:
        return max(0, int((time.perf_counter() - self._started) * 1000))

    async def record_success(self, response: ChatResponse, *, route: str) -> None:
        """写入成功记录并持久化本轮会话；同一实例只写入一次。"""
        if self._written:
            return
        self._written = True
        steps = response.steps or []
        prompt_tokens, completion_tokens = get_chat_usage_totals()
        row = AgentChatCall(
            tenant_id=self.ctx.tenant_id,
            agent_id=self.agent_id,
            conversation_id=self.conversation_id,
            trace_id=get_trace_id(),
            actor_user_id=self.ctx.user_id,
            status="success",
            route=route,
            query_preview=self.query_preview,
            answer_preview=preview_text(response.answer),
            latency_ms=self._latency_ms(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            step_count=len(steps),
            tool_call_count=count_tool_calls(steps),
            meta={"media_count": self.media_count},
            steps_summary=build_steps_summary(steps),
            source=self.ctx.auth_via,
        )
        self.db.add(row)
        await self.db.flush()
        await persist_chat_turn(
            self.db,
            self.ctx,
            self.agent_id,
            self.body,
            response=response,
            trace_id=get_trace_id(),
            user_query=self.user_query,
        )

    async def record_failure(
        self,
        exc: Exception,
        *,
        route: str,
        response: ChatResponse | None = None,
    ) -> None:
        """写入失败记录；合规拦截记为 blocked，其余记为 failed。"""
        if self._written:
            return
        self._written = True
        status = "blocked" if is_compliance_block(exc) else "failed"
        steps = (response.steps if response else None) or []
        answer = response.answer if response else ""
        prompt_tokens, completion_tokens = get_chat_usage_totals()
        row = AgentChatCall(
            tenant_id=self.ctx.tenant_id,
            agent_id=self.agent_id,
            conversation_id=self.conversation_id,
            trace_id=get_trace_id(),
            actor_user_id=self.ctx.user_id,
            status=status,
            route=route,
            query_preview=self.query_preview,
            answer_preview=preview_text(answer),
            latency_ms=self._latency_ms(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            step_count=len(steps),
            tool_call_count=count_tool_calls(steps),
            error_code=str(getattr(exc, "code", None) or type(exc).__name__),
            error_message=preview_text(getattr(exc, "message", str(exc)), max_len=500),
            meta={"media_count": self.media_count},
            steps_summary=build_steps_summary(steps) if steps else None,
            source=self.ctx.auth_via,
        )
        self.db.add(row)
        await self.db.flush()
        await persist_chat_turn(
            self.db,
            self.ctx,
            self.agent_id,
            self.body,
            response=response,
            trace_id=get_trace_id(),
            user_query=self.user_query,
        )


class AgentCallRecordService(BaseService):
    """对话调用记录的查询服务（列表、详情及关联日志）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._agent_repo = AgentRepository(db)

    async def _ensure_agent(self, agent_id: UUID) -> None:
        agent = await self._agent_repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

    async def _attach_usernames(self, rows: list[AgentChatCall]) -> list[AgentCallRecordOut]:
        user_ids = {row.actor_user_id for row in rows if row.actor_user_id}
        username_by_id: dict[UUID, str] = {}
        if user_ids:
            result = await self.db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
            username_by_id = {uid: name for uid, name in result.all()}
        out: list[AgentCallRecordOut] = []
        for row in rows:
            item = AgentCallRecordOut.model_validate(row)
            if row.actor_user_id:
                item.actor_username = username_by_id.get(row.actor_user_id)
            out.append(item)
        return out

    async def _load_related_tool_logs(self, row: AgentChatCall) -> list[ToolInvocationLogOut]:
        start, end = correlation_window(row.created_at, row.latency_ms)
        filters = tenant_filters(self.ctx, ToolInvocationLog.tenant_id) + [
            ToolInvocationLog.agent_id == row.agent_id,
            ToolInvocationLog.created_at >= start,
            ToolInvocationLog.created_at <= end,
        ]
        stmt = select(ToolInvocationLog).where(*filters).order_by(ToolInvocationLog.created_at.asc()).limit(RELATED_LOG_LIMIT)
        items = list((await self.db.scalars(stmt)).all())
        return [ToolInvocationLogOut.model_validate(i) for i in items]

    async def _load_related_hook_logs(self, row: AgentChatCall) -> list[HookExecutionLogOut]:
        if not row.trace_id:
            return []
        filters = tenant_filters(self.ctx, HookExecutionLog.tenant_id) + [
            HookExecutionLog.trace_id == row.trace_id,
        ]
        stmt = select(HookExecutionLog).where(*filters).order_by(HookExecutionLog.created_at.asc()).limit(RELATED_LOG_LIMIT)
        items = list((await self.db.scalars(stmt)).all())
        return [HookExecutionLogOut.model_validate(i) for i in items]

    async def list_records(
        self,
        agent_id: UUID,
        params: PageParams,
        *,
        status: str | None = None,
        conversation_id: str | None = None,
        route: str | None = None,
        q: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> PageResult[AgentCallRecordOut]:
        """分页查询调用记录，支持状态/会话/路由/关键词/时间范围过滤。"""
        await self._ensure_agent(agent_id)
        filters = tenant_filters(self.ctx, AgentChatCall.tenant_id) + [AgentChatCall.agent_id == agent_id]
        if status:
            filters.append(AgentChatCall.status == status)
        if conversation_id:
            filters.append(AgentChatCall.conversation_id == conversation_id)
        if route:
            filters.append(AgentChatCall.route == route)
        if q:
            like = f"%{q.strip()}%"
            filters.append(
                or_(
                    AgentChatCall.query_preview.ilike(like),
                    AgentChatCall.answer_preview.ilike(like),
                    AgentChatCall.trace_id.ilike(like),
                )
            )
        if from_dt:
            filters.append(AgentChatCall.created_at >= from_dt)
        if to_dt:
            filters.append(AgentChatCall.created_at <= to_dt)

        total = await self.db.scalar(select(func.count()).select_from(AgentChatCall).where(*filters))
        stmt = select(AgentChatCall).where(*filters).order_by(AgentChatCall.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = list((await self.db.scalars(stmt)).all())
        return PageResult(
            items=await self._attach_usernames(items),
            total=int(total or 0),
            page=params.page,
            size=params.size,
        )

    async def get_record(self, agent_id: UUID, call_id: UUID) -> AgentCallRecordDetailOut:
        """获取调用记录详情，并附带时间窗内关联的工具与钩子日志。"""
        await self._ensure_agent(agent_id)
        row = await self.db.get(AgentChatCall, call_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("调用记录不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        items = await self._attach_usernames([row])
        base = items[0]
        return AgentCallRecordDetailOut(
            **base.model_dump(),
            meta=dict(row.meta or {}),
            steps_summary=row.steps_summary,
            related_tool_logs=await self._load_related_tool_logs(row),
            related_hook_logs=await self._load_related_hook_logs(row),
        )


def parse_call_record_datetime(value: str | None) -> datetime | None:
    """解析查询参数中的日期/时间串为 UTC ``datetime``，支持仅日期（按当日 0 点）。"""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) == 10:
        text = f"{text}T00:00:00+00:00"
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
