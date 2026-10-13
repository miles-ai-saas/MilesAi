"""
流程 L1：版本化 graph_json、发布、试运行与 LangGraph 编译预览。

与知识库
--------
``run(..., kb_ids=...)`` 将 id 列表注入 ``RunContext``，画布 **KnowledgeSearch** 在未配置
节点级 ``kb_id`` 时使用该列表（与 Agent 发布流程对话行为一致）。

智能体绑定 ``published_flow_id`` 后由 ``AgentService.chat`` 构造 ``RunContext`` 并执行，
不经过本 Service 的调试 API。

子模块：``crud`` / ``versions`` / ``run``；对外 ``from …services.flow import FlowService``。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext
from miles_portal.tenant.flows.services.flow.crud import FlowCrudMixin
from miles_portal.tenant.flows.services.flow.run import FlowRunMixin
from miles_portal.tenant.flows.services.flow.versions import FlowVersionsMixin


class FlowService(FlowRunMixin, FlowVersionsMixin, FlowCrudMixin):
    """保存画布即新版本；智能体绑定 published_flow_id 后由 AgentService 执行。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        FlowCrudMixin.__init__(self, db, ctx)
