"""画布 SubFlow/LoopNode 子流程图加载器（L1 装配）。

``build_subflow_graph_loader`` 构造 ``RunContext.load_subflow_graph`` 回调：短会话
构造 ``FlowRepository`` 并委托 ``resolve_subflow_graph`` 按 published/pinned 策略
加载子图 graph_json，供 flow_runtime SubFlow/LoopNode 节点使用；装配点为
chat_rag.flow_run_context 与 flows flow debug-run。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from miles_ai.flow_runtime.subflow.resolve import resolve_subflow_graph
from miles_core.infra.db import short_db_session
from miles_portal.tenant.flows.repositories.flow import FlowRepository


def build_subflow_graph_loader() -> Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]:
    """构造 RunContext.load_subflow_graph 回调（内部短会话 + FlowRepository）。"""

    async def _loader(node_data: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        tid = UUID(str(tenant_id))
        async with short_db_session() as db:
            return await resolve_subflow_graph(FlowRepository(db), node_data, tid)

    return _loader
