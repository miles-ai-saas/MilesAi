"""agent 对话工具执行器（L1，适配 L3 中性契约）。

``AgentToolExecutor`` 实现 ``tool_agent.tool_contract.ToolExecutor``：meta 委托
``resolve_tool_meta``（dict 原样返回），invoke 委托 ``invoke_tool_with_context``
并把 ``ToolConfirmationRequired`` 转 L3 中性 ``ToolConfirmationSignal``。db/ctx 与
执行上下文（agent_id/actor_user_id/invoke_source）在构造时捕获，供
``tool_agent.loop.run_tool_calling_chat`` 经 ``tool_executor`` 参数注入使用。

``ShortSessionAgentToolExecutor`` 每 meta/invoke 自开 ``AsyncSessionLocal``，成功
或确认信号（需持久化 ``confirmation_required`` 审计日志）时 commit，仅真实
执行异常 rollback，使 tool_agent 循环期间不占用请求会话连接。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import AsyncSessionLocal
from miles_core.tenant import TenantContext
from miles_integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal
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


class ShortSessionAgentToolExecutor:
    """短会话对话工具执行器：每次 meta/invoke 新开会话并提交/回滚。"""

    def __init__(
        self,
        ctx: TenantContext,
        *,
        agent_id: UUID | None,
        actor_user_id: UUID | None,
        invoke_source: str = "agent",
    ) -> None:
        self._ctx = ctx
        self._agent_id = agent_id
        self._actor_user_id = actor_user_id
        self._invoke_source = invoke_source

    async def meta(self, slug: str, *, tool_id: UUID | None = None) -> dict[str, Any]:
        """短会话解析工具元信息。"""
        async with AsyncSessionLocal() as db:
            try:
                result = await resolve_tool_meta(db, self._ctx, slug, tool_id=tool_id)
                await db.commit()
                return result
            except Exception:
                await db.rollback()
                raise

    async def invoke(
        self,
        slug: str,
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        tool_id: UUID | None = None,
    ) -> dict[str, Any]:
        """短会话执行工具；确认路径 commit 审计日志后再抛 Signal。"""
        async with AsyncSessionLocal() as db:
            try:
                result = await invoke_tool_with_context(
                    db,
                    self._ctx,
                    slug,
                    params,
                    tool_id=tool_id,
                    confirmed=confirmed,
                    actor_user_id=self._actor_user_id,
                    agent_id=self._agent_id,
                    invoke_source=self._invoke_source,
                )
                await db.commit()
                return result
            except ToolConfirmationRequired as exc:
                # halt_for_confirmation 已写入 confirmation_required 审计日志，须提交
                await db.commit()
                raise ToolConfirmationSignal(
                    exc.slug,
                    exc.tool_name,
                    exc.tool_description,
                    exc.params,
                ) from None
            except Exception:
                await db.rollback()
                raise


def build_agent_tool_executor(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    agent_id: UUID | None,
    actor_user_id: UUID | None,
    invoke_source: str = "agent",
) -> AgentToolExecutor:
    """构造会话绑定的对话工具执行器（兼容仍需复用请求会话的调用方）。"""
    return AgentToolExecutor(
        db,
        ctx,
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        invoke_source=invoke_source,
    )


def build_short_session_agent_tool_executor(
    ctx: TenantContext,
    *,
    agent_id: UUID | None,
    actor_user_id: UUID | None,
    invoke_source: str = "agent",
) -> ShortSessionAgentToolExecutor:
    """构造短会话对话工具执行器（tool_agent 循环装配点）。"""
    return ShortSessionAgentToolExecutor(
        ctx,
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        invoke_source=invoke_source,
    )
