"""结构不变量：Celery Worker 可达的模块不得再引用全局 ``AsyncSessionLocal``。

Celery 任务用 ``asyncio.run``，每次新建事件循环；全局 engine 池里属于上一个 loop 的
asyncpg 连接一旦复用即抛 ``RuntimeError: ... got Future attached to a different loop``，
定时智能体任务据此约半数失败。这些模块必须统一走 ``short_db_session``（Worker 内绑当前
loop 的 engine，API/CLI 单 loop 进程回退全局）。

逐站点的行为护栏在各自测试文件里（把全局会话换成「调用即炸」替身）；本文件是不变量
底网：即便某个站点的行为用例被绕过或删掉，只要模块命名空间里又出现 ``AsyncSessionLocal``
就会红。

**这 13 个模块是怎么来的**：清单的判据是「因 Worker 可达而**必须**用
``short_db_session``」，而非「Task 1 改了哪 10 个文件」——若按后者维护，新出现
（或当时被漏掉）的站点就永远进不了网，``progress.py`` 正是这样漏过一轮的。
本文件的 ``test_list_matches_every_short_db_session_call_site`` 直接扫源码交叉核对，
故后续新增站点会立刻以「清单缺项」的形态失败，而不是静默留在网外。

各模块的 Worker 可达路径：

- ``miles_ai...rag_qa``：定时智能体走 LangGraph RAG 时的 ``retrieve`` 节点
- ``miles_ai...image_generate`` / ``...video_generate``：画布生图/生视频节点（Agent 对话 /
  定时任务跑画布流程）
- ``miles_ai...rag_nodes``：画布 ``KnowledgeSearch`` 节点
- ``miles_ai...jobs.progress``：Celery 生成任务（``job_execution``）读写的进度/取消状态
- ``miles_portal...models.services.usage``：``FlowUsageSink.record`` 画布用量落库
- ``miles_portal...tools.services.flow_invoker``：画布平台工具执行
- ``miles_portal...flows.services.run_context``：画布模型解析
- ``miles_portal...flows.services.subflow_loader``：子流程图加载
- ``miles_portal...prompts.services.template_loader``：提示词模板 live 引用加载
- ``miles_portal...compliance.services.scan_words_loader``：敏感词表加载
- ``miles_portal...agents.services.agent.chat_rag``：Agent 对话/定时任务的 RAG 检索短会话
- ``miles_portal...attachments.services.media_reader``：每调用新开短会话的媒体读取器

**刻意排除**（``EXCLUDED_INFRA_MODULES``）：

- ``miles_core.infra.db.async_session`` —— 它就是 ``short_db_session`` 的回退实现，
  必须保留对 ``AsyncSessionLocal`` 的引用（API / CLI 单 loop 进程靠它工作）；
- ``miles_core.infra.db`` —— 仅 re-export 的 barrel，不含会话逻辑。

刻意**不在**清单里的单 loop 进程站点（``EXCLUDED_SINGLE_LOOP_MODULES``）：
``miles_core.risk.enforce``、``miles_portal.tenant.agents.ws.chat``、
``miles_portal.tenant.agents.ws.job_watch``（仅由 WebSocket 端点调用）、
``miles_server.scripts.*``（CLI 脚本）。
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

# Celery Worker 内可达、必须用 short_db_session 的模块（按 dotted path 排序）。
EXPECTED_SHORT_SESSION_MODULES: tuple[str, ...] = (
    "miles_ai.flow_runtime.nodes.image_generate",
    "miles_ai.flow_runtime.nodes.rag_nodes",
    "miles_ai.flow_runtime.nodes.video_generate",
    "miles_ai.integrations.generative.jobs.progress",
    "miles_ai.integrations.langgraph.graphs.rag_qa",
    "miles_portal.tenant.agents.services.agent.chat_rag",
    "miles_portal.tenant.attachments.services.media_reader",
    "miles_portal.tenant.compliance.services.scan_words_loader",
    "miles_portal.tenant.flows.services.run_context",
    "miles_portal.tenant.flows.services.subflow_loader",
    "miles_portal.tenant.models.services.usage",
    "miles_portal.tenant.prompts.services.template_loader",
    "miles_portal.tenant.tools.services.flow_invoker",
)

# 有意保留全局会话引用的基础设施模块（回退实现与其 barrel）。
EXCLUDED_INFRA_MODULES: tuple[str, ...] = (
    "miles_core.infra.db.async_session",
    "miles_core.infra.db",
)

# 有意留在全局会话上的单 loop 站点（不在 Worker 子树内）。
EXCLUDED_SINGLE_LOOP_MODULES: tuple[str, ...] = (
    "miles_core.risk.enforce",
    "miles_portal.tenant.agents.ws.chat",
    "miles_portal.tenant.agents.ws.job_watch",
)

_PKG_ROOT = Path(__file__).resolve().parents[2] / "packages"
_SHORT_SESSION_CALL_SITE_RE = re.compile(r"\bshort_db_session\(")


def _discover_short_session_call_sites() -> set[str]:
    """扫源码找出所有出现 ``short_db_session(`` 的模块 dotted path。

    匹配的是**文本**而不是语法树：``short_db_session(`` 出现在注释、docstring 或字符串
    字面量里同样计入（``async def short_db_session(...)`` 的定义行也计入）。这是有意的
    过近似——本函数的用途是「不让新站点静默留在网外」，而漏报才会造成那种后果；误报
    只会在下面 ``missing`` 断言里多出一个模块名，确认后补进清单或改掉措辞即可。

    ``__init__.py`` 归一化为其包路径（``a/b/__init__.py`` → ``a.b``），与
    ``EXCLUDED_INFRA_MODULES`` 里 barrel 的拼法一致，避免两种拼法日后分叉。
    被排除的基础设施模块由调用方剔除。
    """
    found: set[str] = set()
    for path in sorted(_PKG_ROOT.glob("*/src/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if not _SHORT_SESSION_CALL_SITE_RE.search(text):
            continue
        # packages/<pkg>/src/<a>/<b>/<mod>.py → <a>.<b>.<mod>（__init__ 去尾）
        src_index = path.parts.index("src")
        dotted = ".".join(path.parts[src_index + 1 :]).removesuffix(".py")
        found.add(dotted.removesuffix(".__init__"))
    return found


@pytest.mark.parametrize("path", EXPECTED_SHORT_SESSION_MODULES)
def test_worker_reachable_modules_use_short_session(path: str) -> None:
    """命名空间里没有全局会话、且有短会话——回退或改名都会让本用例红。"""
    mod = importlib.import_module(path)
    assert not hasattr(mod, "AsyncSessionLocal"), f"{path} 不得直接引用全局会话（见 spec §10）"
    assert hasattr(mod, "short_db_session"), f"{path} 应改用 short_db_session"


@pytest.mark.parametrize("path", EXCLUDED_INFRA_MODULES)
def test_fallback_implementation_keeps_the_global_reference(path: str) -> None:
    """回退实现与其 barrel 必须两个符号都在：去掉全局引用会让 API/CLI 路径失效。"""
    mod = importlib.import_module(path)
    assert hasattr(mod, "AsyncSessionLocal"), f"{path} 是回退实现/barrel，必须保留全局会话引用"
    assert hasattr(mod, "short_db_session"), f"{path} 应导出 short_db_session"


def test_list_matches_every_short_db_session_call_site() -> None:
    """清单必须等于「全仓所有 short_db_session 调用点」减去有意排除的基础设施模块。

    这条交叉核对正是为了防止本文件重演「清单只抄 Task 1 触碰过的文件」而漏站点：
    新增（或漏记）的站点会在这里以清单缺项的形态失败，而不是静默留在网外。
    """
    discovered = _discover_short_session_call_sites() - set(EXCLUDED_INFRA_MODULES)
    expected = set(EXPECTED_SHORT_SESSION_MODULES)

    missing = sorted(discovered - expected)
    stale = sorted(expected - discovered)
    assert not missing, f"以下模块在用 short_db_session 却不在清单里，请补入并说明其 Worker 可达路径：{missing}"
    assert not stale, f"清单里以下模块已不再调用 short_db_session，请移除或说明原因：{stale}"


def test_expected_module_list_is_exactly_the_worker_sites() -> None:
    """清单互斥且计数明确：防止顺手把单 loop 站点拉进来，或漏掉多轮加入的站点。"""
    assert len(EXPECTED_SHORT_SESSION_MODULES) == 13
    assert len(set(EXPECTED_SHORT_SESSION_MODULES)) == 13
    excluded = set(EXCLUDED_SINGLE_LOOP_MODULES) | set(EXCLUDED_INFRA_MODULES)
    assert excluded.isdisjoint(EXPECTED_SHORT_SESSION_MODULES)
