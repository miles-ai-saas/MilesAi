"""智能体对话（同步与 HTTP SSE）。"""

from uuid import UUID

from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.deps_api_auth import require_agent_chat_auth
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.views.agents.deps import agent_svc
from miles_portal.tenant.agents.views.agents.router import router


@router.post("/{agent_id}/chat", response_model=ApiResponse[ChatResponse])
async def chat_agent(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_agent_chat_auth),
    db: AsyncSession = Depends(get_db),
):
    """主对话入口：合规 → 钩子 → A2A/子 Agent/流程/RAG 路由（见 AgentService.chat）。"""
    return ok(await agent_svc(db, ctx).chat(agent_id, body))


@router.post("/{agent_id}/chat/stream")
async def chat_agent_stream(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_agent_chat_auth),
):
    """HTTP SSE 对话流：事件类型与 WS 对齐（``chat.delta`` / ``chat.done`` / ``chat.error``）。

    工作台优先 WS；本端点供 API/脚本/无法升级 WebSocket 的客户端使用。
    请求体与 ``POST …/chat`` 相同；响应为 ``text/event-stream``。
    """
    from miles_portal.tenant.agents.services.chat_sse import iter_agent_chat_sse

    return StreamingResponse(
        iter_agent_chat_sse(ctx, agent_id, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
