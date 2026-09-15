"""结构不变量：Celery Worker 可达的模块不得再引用全局 ``AsyncSessionLocal``。

Celery 任务用 ``asyncio.run``，每次新建事件循环；全局 engine 池里属于上一个 loop 的
asyncpg 连接一旦复用即抛 ``RuntimeError: ... got Future attached to a different loop``，
定时智能体任务据此约半数失败。这些模块必须统一走 ``short_db_session``（Worker 内绑当前
loop 的 engine，API/CLI 单 loop 进程回退全局）。

逐站点的行为护栏在各自测试文件里（把全局会话换成「调用即炸」替身）；本文件是不变量
底网：即便某个站点的行为用例被绕过或删掉，只要模块命名空间里又出现 ``AsyncSessionLocal``
就会红。

**为什么是这 10 个模块**：它们全部落在 ``agent_schedule`` → ``get_worker_session()`` 的
调用子树内（spec §10.4）。刻意**不在**清单里的单 loop 进程站点：
``miles_core.risk.enforce``、``miles_portal.tenant.agents.ws.chat``、
``miles_portal.tenant.agents.ws.job_watch``（仅由 WebSocket 端点调用）、
``miles_server.scripts.*``（CLI 脚本），以及 ``async_session.py`` 自身——
后者就是 ``short_db_session`` 的回退实现，理应保留全局引用。
"""

from __future__ import annotations

import importlib

import pytest

# Celery Worker 内可达、必须用 short_db_session 的模块（spec §10.4 的 10 个文件）。
EXPECTED_SHORT_SESSION_MODULES: tuple[str, ...] = (
    "miles_ai.integrations.langgraph.graphs.rag_qa",
    "miles_ai.flow_runtime.nodes.image_generate",
    "miles_ai.flow_runtime.nodes.video_generate",
    "miles_ai.flow_runtime.nodes.rag_nodes",
    "miles_portal.tenant.models.services.usage",
    "miles_portal.tenant.tools.services.flow_invoker",
    "miles_portal.tenant.flows.services.run_context",
    "miles_portal.tenant.flows.services.subflow_loader",
    "miles_portal.tenant.prompts.services.template_loader",
    "miles_portal.tenant.compliance.services.scan_words_loader",
)

# 有意留在全局会话上的单 loop 站点（不在 Worker 子树内）。
EXCLUDED_SINGLE_LOOP_MODULES: tuple[str, ...] = (
    "miles_core.risk.enforce",
    "miles_portal.tenant.agents.ws.chat",
    "miles_portal.tenant.agents.ws.job_watch",
)


@pytest.mark.parametrize("path", EXPECTED_SHORT_SESSION_MODULES)
def test_worker_reachable_modules_use_short_session(path: str) -> None:
    """命名空间里没有全局会话、且有短会话——回退或改名都会让本用例红。"""
    mod = importlib.import_module(path)
    assert not hasattr(mod, "AsyncSessionLocal"), f"{path} 不得直接引用全局会话（见 spec §10）"
    assert hasattr(mod, "short_db_session"), f"{path} 应改用 short_db_session"


def test_expected_module_list_is_exactly_the_worker_sites() -> None:
    """清单互斥且计数明确：防止顺手把单 loop 站点拉进来，或漏掉多轮加入的站点。"""
    assert len(EXPECTED_SHORT_SESSION_MODULES) == 10
    assert len(set(EXPECTED_SHORT_SESSION_MODULES)) == 10
    assert set(EXCLUDED_SINGLE_LOOP_MODULES).isdisjoint(EXPECTED_SHORT_SESSION_MODULES)
