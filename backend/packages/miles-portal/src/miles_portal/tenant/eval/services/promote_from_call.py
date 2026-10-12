"""从智能体调用记录升格为评测用例。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.models.agent.chat_call import AgentChatCall
from miles_core.models.agent.chat_session import AgentChatMessage
from miles_core.models.eval import EvalCase
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters


async def resolve_turn_texts(
    db: AsyncSession,
    *,
    call: AgentChatCall,
    prefer_session_text: bool = True,
) -> tuple[str, str, bool]:
    """返回 (query, answer, used_session)。无会话全文时退回 preview。"""
    query = (call.query_preview or "").strip()
    answer = (call.answer_preview or "").strip()
    used_session = False

    if prefer_session_text and call.conversation_id:
        cid = call.conversation_id.strip()
        assistant: AgentChatMessage | None = None
        if call.trace_id:
            assistant = (
                await db.execute(
                    select(AgentChatMessage)
                    .where(
                        AgentChatMessage.session_id == cid,
                        AgentChatMessage.agent_id == call.agent_id,
                        AgentChatMessage.tenant_id == call.tenant_id,
                        AgentChatMessage.role == "assistant",
                        AgentChatMessage.trace_id == call.trace_id,
                    )
                    .order_by(AgentChatMessage.sort_index.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        if assistant is None and call.created_at is not None:
            # 无 trace 时取会话中最接近调用时间的 assistant 消息
            assistant = (
                await db.execute(
                    select(AgentChatMessage)
                    .where(
                        AgentChatMessage.session_id == cid,
                        AgentChatMessage.agent_id == call.agent_id,
                        AgentChatMessage.tenant_id == call.tenant_id,
                        AgentChatMessage.role == "assistant",
                        AgentChatMessage.created_at <= call.created_at,
                    )
                    .order_by(AgentChatMessage.created_at.desc(), AgentChatMessage.sort_index.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        if assistant is not None:
            user_msg = (
                await db.execute(
                    select(AgentChatMessage)
                    .where(
                        AgentChatMessage.session_id == cid,
                        AgentChatMessage.role == "user",
                        AgentChatMessage.sort_index < assistant.sort_index,
                    )
                    .order_by(AgentChatMessage.sort_index.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if user_msg and (user_msg.content or "").strip():
                query = user_msg.content.strip()
                used_session = True
            if (assistant.content or "").strip():
                answer = assistant.content.strip()
                used_session = True

    return query, answer, used_session


async def promote_case_from_call(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    dataset_id: UUID,
    agent_id: UUID,
    call_id: UUID,
    name: str | None = None,
    expected: dict | None = None,
    prefer_session_text: bool = True,
) -> EvalCase:
    """校验 call 归属后写入 EvalCase；成功调用默认 expected.contains=答案全文。"""
    filters = tenant_filters(ctx, AgentChatCall.tenant_id) + [
        AgentChatCall.id == call_id,
        AgentChatCall.agent_id == agent_id,
    ]
    call = (await db.execute(select(AgentChatCall).where(*filters))).scalar_one_or_none()
    if not call:
        raise NotFoundError("调用记录不存在")
    assert_tenant_access(ctx, call.tenant_id)

    if call.status != "success":
        raise BadRequestError("仅支持从成功调用升格用例")

    query, answer, _used = await resolve_turn_texts(db, call=call, prefer_session_text=prefer_session_text)
    if not query:
        raise BadRequestError("调用记录缺少可用的用户问题文本")

    if expected is None:
        expected = {"contains": answer} if answer else None

    sort_index = int(
        await db.scalar(
            select(func.coalesce(func.max(EvalCase.sort_index), -1)).where(
                EvalCase.dataset_id == dataset_id,
                EvalCase.tenant_id == ctx.tenant_id,
            )
        )
        or -1
    ) + 1

    case_name = (name or "").strip() or None
    if not case_name:
        case_name = (query[:48] + "…") if len(query) > 48 else query

    # lineage 写入 expected 旁路键，打分逻辑只认 exact/contains/contains_all/rubric
    expected_payload = dict(expected) if expected else {}
    expected_payload["_source"] = {
        "call_id": str(call.id),
        "agent_id": str(call.agent_id),
        "trace_id": call.trace_id,
    }

    row = EvalCase(
        tenant_id=ctx.tenant_id,
        dataset_id=dataset_id,
        name=case_name,
        query=query,
        expected=expected_payload,
        sort_index=sort_index,
    )
    db.add(row)
    await db.flush()
    return row
