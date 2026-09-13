"""agent 对话工具执行器（L1，适配 L3 中性契约）。

``AgentToolExecutor`` 实现 ``tool_agent.tool_contract.ToolExecutor``：meta 委托
``resolve_tool_meta``（dict 原样返回），invoke 委托 ``invoke_tool_with_context``
并把 ``ToolConfirmationRequired`` 转 L3 中性 ``ToolConfirmationSignal``。db/ctx 与
执行上下文（agent_id/actor_user_id/invoke_source）在构造时捕获，供
``tool_agent.loop.run_tool_calling_chat`` 经 ``tool_executor`` 参数注入使用。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal
from miles_core.tenant import TenantContext
from miles_portal.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from miles_portal.tenant.tools.invoke import invoke_tool_with_context


class AgentToolExecutor:
    """对话工具执行器：meta 解析 + invoke（确认信号中性转换）。"""

    def __init__(
        self,
        db: AsyncSession,
        ctx: TenantContext,
        *,
        agent_id: UUID | None,
        actor_user_id: UUID | None,
        invoke_source: str = "agent",
    ) -> None:
        self._db = db
        self._ctx = ctx
        self._agent_id = agent_id
        self._actor_user_id = actor_user_id
        self._invoke_source = invoke_source

    async def meta(self, slug: str, *, tool_id: UUID | None = None) -> dict[str, Any]:
        """解析工具元信息（内置/custom/MCP 统一结构），委托 ``resolve_tool_meta``。"""
        return await resolve_tool_meta(self._db, self._ctx, slug, tool_id=tool_id)

    async def invoke(
        self,
        slug: str,
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        tool_id: UUID | None = None,
    ) -> dict[str, Any]:
        """执行工具；需确认时把 ``ToolConfirmationRequired`` 转 L3 中性信号。"""
        try:
            return await invoke_tool_with_context(
                self._db,
                self._ctx,
                slug,
                params,
                tool_id=tool_id,
                confirmed=confirmed,
                actor_user_id=self._actor_user_id,
                agent_id=self._agent_id,
                invoke_source=self._invoke_source,
            )
        except ToolConfirmationRequired as exc:
            raise ToolConfirmationSignal(
                exc.slug,
                exc.tool_name,
                exc.tool_description,
                exc.params,
            ) from None


def build_agent_tool_executor(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    agent_id: UUID | None,
    actor_user_id: UUID | None,
    invoke_source: str = "agent",
) -> AgentToolExecutor:
    """构造对话工具执行器（chat_rag 装配点注入 loop 用）。"""
    return AgentToolExecutor(
        db,
        ctx,
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        invoke_source=invoke_source,
    )
