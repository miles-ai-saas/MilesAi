"""子流程解析/校验所需的最小仓储契约（L3 中性）。

``FlowRepoLike`` 由 L1 ``tenant.flows.repositories.flow.FlowRepository`` 结构满足
（duck-typing）；L3 只按该契约调用，不反向 import tenant。
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

__all__ = ["FlowRepoLike"]


class FlowRepoLike(Protocol):
    """子流程加载/校验所需的最小 Flow 仓储接口。"""

    async def get_by_id(self, entity_id: UUID, *, include_deleted: bool = False) -> Any | None:
        """按 id 取 Flow（软删默认过滤）。"""
        ...

    async def get_version(self, flow_id: UUID, version: int) -> Any | None:
        """按 flow_id + 版本号取 FlowVersion（含 graph_json）。"""
        ...
