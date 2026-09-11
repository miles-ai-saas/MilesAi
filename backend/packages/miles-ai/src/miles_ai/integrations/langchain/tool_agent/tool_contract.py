"""agent 对话工具执行/确认契约（L3 中性，L1 适配实现注入）。

``loop.py`` 只依赖本契约：meta 解析返回 dict（键 ``slug``/``name``/``description``/
``require_confirmation``/``source``/``tool_id``）；invoke 需确认时抛 ``ToolConfirmationSignal``
（字段与 ``tenant.tools.confirmation.ToolConfirmationRequired`` 同名同构）。
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

__all__ = ["ToolConfirmationSignal", "ToolExecutor"]


class ToolConfirmationSignal(Exception):
    """工具执行需用户确认（L1 executor 自 tenant 信号转换后抛出）。"""

    def __init__(
        self,
        slug: str,
        tool_name: str,
        tool_description: str | None,
        params: dict,
    ) -> None:
        self.slug = slug
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.params = params
        super().__init__(f"工具「{tool_name}」需要确认后执行")


class ToolExecutor(Protocol):
    """L1 注入的对话工具执行器（duck-typed，loop 侧无需真实子类）。"""

    async def meta(self, slug: str, *, tool_id: UUID | None = None) -> dict[str, Any]:
        """解析工具元数据；不存在抛 ``BadRequestError``。返回键见模块 docstring。"""
        ...

    async def invoke(
        self,
        slug: str,
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        tool_id: UUID | None = None,
    ) -> dict[str, Any]:
        """执行工具；需确认且未确认时抛 ``ToolConfirmationSignal``。"""
        ...
