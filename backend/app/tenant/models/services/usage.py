"""记录模型 Token 用量。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import ModelConfig
from app.models.model.usage_log import ModelUsageLog

_chat_usage_acc: ContextVar[tuple[int, int] | None] = ContextVar("_chat_usage_acc", default=None)


def begin_chat_usage_accumulation() -> Token[tuple[int, int] | None]:
    """单轮 Agent chat 开始时重置 Token 累计（供调用记录写入）。"""
    return _chat_usage_acc.set((0, 0))


def end_chat_usage_accumulation(token: Token[tuple[int, int] | None]) -> None:
    _chat_usage_acc.reset(token)


def get_chat_usage_totals() -> tuple[int, int]:
    val = _chat_usage_acc.get()
    if val is None:
        return (0, 0)
    return val


@dataclass(frozen=True)
class UsageRecordContext:
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
    total = max(0, prompt_tokens) + max(0, completion_tokens)
    if total <= 0:
        return
    if ctx.source == "chat" and ctx.source_id is not None:
        acc = _chat_usage_acc.get()
        if acc is not None:
            p, c = acc
            _chat_usage_acc.set((p + max(0, prompt_tokens), c + max(0, completion_tokens)))
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


async def record_litellm_response_usage(ctx: UsageRecordContext, response: Any) -> None:
    """从 LiteLLM completion 响应提取 Token 并写入用量日志。"""
    from app.integrations.litellm.adapter import extract_litellm_usage

    prompt_t, completion_t, _ = extract_litellm_usage(response)
    await record_model_usage(ctx, prompt_tokens=prompt_t, completion_tokens=completion_t)


class ChatUsageSink:
    """对话链路的用量记录器：会话 token 累计 + 落 ModelUsageLog。

    实现 L3 ``UsageSink`` 协议，由 L1 装配（如 AgentService、flow 运行入口）
    构造并注入引擎；``source_id`` 为对话 agent_id，用于 chat 用量累计。
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        model: ModelConfig,
        source_id: UUID | None = None,
    ) -> None:
        self._ctx = UsageRecordContext(
            db=db,
            tenant_id=tenant_id,
            model=model,
            source="chat",
            source_id=source_id,
        )

    async def record(self, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        await record_model_usage(
            self._ctx,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
