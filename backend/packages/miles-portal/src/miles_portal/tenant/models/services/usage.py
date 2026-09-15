"""记录模型 Token 用量。"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_core.infra.db import AsyncSessionLocal, short_db_session
from miles_core.models.model import ModelConfig
from miles_core.models.model.usage_log import ModelUsageLog


@dataclass
class ChatUsageAccumulator:
    """单轮 chat 的 token 累计器。

    刻意做成**可变对象**：``_chat_usage_acc`` 里存的是它的引用，记录用量时原地累加。
    若沿用「存元组 + 每次 set() 新元组」，绑定只会写进当前 context——LangGraph 在
    子 task 里执行节点时，父 context 读到的仍是初始值，``AgentChatCall`` 会恒记 0 token。
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    def add(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)

    def totals(self) -> tuple[int, int]:
        return self.prompt_tokens, self.completion_tokens


_chat_usage_acc: ContextVar[ChatUsageAccumulator | None] = ContextVar("_chat_usage_acc", default=None)


def begin_chat_usage_accumulation() -> Token[ChatUsageAccumulator | None]:
    """单轮 Agent chat 开始时重置 Token 累计（供调用记录写入）。"""
    return _chat_usage_acc.set(ChatUsageAccumulator())


def end_chat_usage_accumulation(token: Token[ChatUsageAccumulator | None]) -> None:
    """恢复到本轮 chat 累计前的上下文状态。"""
    _chat_usage_acc.reset(token)


def get_chat_usage_totals() -> tuple[int, int]:
    """返回当前轮次累计的 (prompt_tokens, completion_tokens)。"""
    acc = _chat_usage_acc.get()
    if acc is None:
        return (0, 0)
    return acc.totals()


@dataclass(frozen=True)
class UsageRecordContext:
    """记录一次模型用量所需的上下文（会话、租户、模型、来源）。"""

    db: AsyncSession
    tenant_id: UUID
    model: ModelConfig
    source: str = "chat"
    source_id: UUID | None = None


async def record_model_usage(
    ctx: UsageRecordContext,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """写 ``ModelUsageLog`` 并 flush；chat 来源同时累加到上下文变量。"""
    total = max(0, prompt_tokens) + max(0, completion_tokens)
    if total <= 0:
        return
    if ctx.source == "chat" and ctx.source_id is not None:
        acc = _chat_usage_acc.get()
        if acc is not None:
            # 原地累加，不重新绑定：子 task 里的写入必须能被父 context 看见
            acc.add(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    row = ModelUsageLog(
        tenant_id=ctx.tenant_id,
        model_config_id=ctx.model.id,
        model_name=ctx.model.name,
        source=ctx.source,
        source_id=ctx.source_id,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
        total_tokens=total,
    )
    ctx.db.add(row)
    await ctx.db.flush()


class ChatUsageSink:
    """对话链路的用量记录器：会话 token 累计 + 落 ModelUsageLog。

    实现 L3 ``UsageSink`` 协议，由 L1 装配（如 AgentService、flow 运行入口）
    构造并注入引擎；``source_id`` 为对话 agent_id，用于 chat 用量累计。

    ``record`` 自开短会话并提交，**不借用调用方会话**：生成阶段的 LLM 调用之间
    会记录用量，若挂在请求事务上就等于整段生成期间占住一个连接。token 仍累加到
    ``_chat_usage_acc`` ContextVar（与 Session 无关），供 ``AgentChatCall`` 汇总。
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        model: ModelConfig,
        source_id: UUID | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._model = model
        self._source_id = source_id

    async def record(self, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """实现 ``UsageSink`` 协议：自开短会话写 chat 来源用量并提交。"""
        # 与 ``record_model_usage`` 内的零用量短路重复，但这里必须保留：只有在此处
        # 提前返回，才不会执行 ``short_db_session()`` 去**打开一个会话/连接**。
        # 删掉它会让空记录也占用一次连接，违背本类「生成期间不占用调用方连接」的初衷。
        if max(0, prompt_tokens) + max(0, completion_tokens) <= 0:
            return
        async with short_db_session() as db:
            await record_model_usage(
                UsageRecordContext(
                    db=db,
                    tenant_id=self._tenant_id,
                    model=self._model,
                    source="chat",
                    source_id=self._source_id,
                ),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            await db.commit()


class FlowUsageSink:
    """画布 LLM 节点的用量记录器（实现 L3 ``UsageSink`` 协议）。

    与 ``ChatUsageSink`` 的差异：画布节点可各自指定模型，故本 sink 按**解析后的
    模型**构造（经 ``RunContext.usage_sink_factory`` 逐次产出）；``record`` 自开
    短会话落 ``ModelUsageLog``（``source="flow"``）并提交，不依赖调用方会话存续。
    因 ``source`` 非 ``chat``，不参与会话 token 累计。
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        model: ModelConfig,
        source_id: UUID | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._model = model
        self._source_id = source_id

    async def record(self, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """实现 ``UsageSink`` 协议：自开短会话写 flow 来源用量并提交。"""
        if max(0, prompt_tokens) + max(0, completion_tokens) <= 0:
            return
        async with AsyncSessionLocal() as db:
            await record_model_usage(
                UsageRecordContext(
                    db=db,
                    tenant_id=self._tenant_id,
                    model=self._model,
                    source="flow",
                    source_id=self._source_id,
                ),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            await db.commit()


def make_flow_usage_sink_factory(
    tenant_id: UUID,
    *,
    source_id: UUID | None = None,
) -> Callable[[ModelConfig], UsageSink]:
    """构造画布用量 sink 工厂：LLM 节点解析出模型后按模型产出 sink。"""

    def _factory(model: ModelConfig) -> UsageSink:
        return FlowUsageSink(tenant_id=tenant_id, model=model, source_id=source_id)

    return _factory
