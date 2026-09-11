"""LiteLLM 用量记录回调（L3 中立，不依赖 tenant 域）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UsageSink(Protocol):
    """一次对话/工具调用的 Token 用量记录器。

    由 L1 装配实现（如 ``tenant.models.services.usage.ChatUsageSink``）并
    随引擎调用注入；adapter 只调用本协议，不感知落库/累计细节。
    """

    async def record(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        """记录一次调用的输入 / 输出 token 数（由实现方决定落库或累计）。"""
        ...
