"""结构不变量：Celery Worker 可达的模块不得再引用全局 ``AsyncSessionLocal``。

Celery 任务用 ``asyncio.run``，每次新建事件循环；全局 engine 池里属于上一个 loop 的
asyncpg 连接一旦复用即抛 ``RuntimeError: ... got Future attached to a different loop``，
定时智能体任务据此约半数失败。这些模块必须统一走 ``short_db_session``（Worker 内绑当前
loop 的 engine，API/CLI 单 loop 进程回退全局）。

逐站点的行为护栏在各自测试文件里（把全局会话换成「调用即炸」替身）；本文件是不变量
底网：即便某个站点的行为用例被绕过或删掉，只要模块**语法树里**又出现 ``AsyncSessionLocal``
就会红。

**这 13 个模块是怎么来的**：清单的判据是「因 Worker 可达而**必须**用
``short_db_session``」，而非「Task 1 改了哪 10 个文件」——若按后者维护，新出现
（或当时被漏掉）的站点就永远进不了网，``progress.py`` 正是这样漏过一轮的。

三处数字口径不同，含义各异，别再混用：

- **10 文件 / 12 处**：本分支 Task 1 实际改动（``git diff`` 口径）；
- **11 文件 / 14 处**：spec §10.4 表枚举的 Worker 同险站点总数（含基点上即已安全的
  ``progress.py`` 2 处）；
- **13 模块**：必须受本文件护栏保护的 Worker 可达模块数（= Task 1 的 10 个 + 此前已是
  ``short_db_session`` 的 ``progress.py`` / ``chat_rag`` / ``media_reader``）。

本文件用 **AST** 交叉核对，两个方向都钉住：

1. ``test_list_matches_every_short_db_session_call_site``——清单 = 全仓**引用**
   ``short_db_session`` 的模块 − 有意排除的基础设施模块。新增（或漏记）的站点立刻以
   「清单缺项」失败。
2. ``test_only_registered_modules_may_touch_the_global_session``——「谁可以碰全局会话」必须
   是**显式登记**的决定：全仓引用 ``AsyncSessionLocal`` 的模块集合必须恰好等于
   ``EXCLUDED_INFRA_MODULES`` + ``EXCLUDED_SINGLE_LOOP_MODULES``。只扫 ``short_db_session(``
   的旧实现看不见最危险的回归形态（新模块直接开全局会话），这里补齐。

扫的是语法树而不是文本：注释、docstring、字符串字面量里的同名文本一律不计（正则时代
「注释里提一句 ``short_db_session()``」会误报，``sync.py`` 实测中招）；函数/类**定义**名也
不计入——定义处不是引用。

**AST 口径的边界**（有意如此，不是遗漏）：判据是「语法树里出现该符号名」，故
① 属性访问或局部同名变量（``a.config.AsyncSessionLocal``、``AsyncSessionLocal = ...``）
会被计入——方向偏保守，最坏是让无关改动变红后补一次登记；
② 动态取用（``getattr(mod, "AsyncSessionLocal")``、kwargs 里的字符串键）不计入——真正的
回归形态是普通的 import + 调用，会被抓住。另：扫描根为 ``packages/*/src/**/*.py``，
今日全仓别处无生产引用；若将来有成员包用非 ``src`` 布局，需同步本扫描根。

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
``miles_core.risk.enforce``（只被 Web 中间件与 Admin 服务调用）、
``miles_portal.tenant.agents.ws.chat``、``miles_portal.tenant.agents.ws.job_watch``
（仅由 WebSocket 端点调用）、``miles_server.scripts.backfill_media_assets`` /
``miles_server.scripts.db_ops``（仅由 Typer CLI 调用）。这些是本文件扫出的**全部**剩余
全局会话引用；任何新增引用都必须在此显式登记并说明其 loop 安全性。
"""

from __future__ import annotations

import ast
import importlib
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

# 有意留在全局会话上的单 loop 站点（不在 Worker 子树内，逐个追溯过调用方）。
EXCLUDED_SINGLE_LOOP_MODULES: tuple[str, ...] = (
    "miles_core.risk.enforce",
    "miles_portal.tenant.agents.ws.chat",
    "miles_portal.tenant.agents.ws.job_watch",
    "miles_server.scripts.backfill_media_assets",
    "miles_server.scripts.db_ops",
)

_PKG_ROOT = Path(__file__).resolve().parents[2] / "packages"


def _referenced_symbols(tree: ast.AST) -> set[str]:
    """语法树里出现过的符号名：``ast.Name`` / 属性访问 ``.attr`` / import 别名。

    注释、docstring、字符串字面量都不是以上任何一种，故同名文本不会计入；函数/类定义名
    （``ast.FunctionDef.name`` 等）同样不计——定义处是声明，不是引用。
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.alias):
            found.add(node.name.rsplit(".", 1)[-1])
    return found


def _module_dotted(path: Path) -> str:
    """``packages/<pkg>/src/<a>/<b>/<mod>.py`` → ``<a>.<b>.<mod>``（``__init__`` 去尾）。"""
    src_index = path.parts.index("src")
    dotted = ".".join(path.parts[src_index + 1 :]).removesuffix(".py")
    return dotted.removesuffix(".__init__")


def _discover_modules_referencing(symbol: str) -> set[str]:
    """扫 ``packages/*/src/**/*.py`` 的语法树，返回引用 ``symbol`` 的模块 dotted path。"""
    found: set[str] = set()
    for path in sorted(_PKG_ROOT.glob("*/src/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if symbol in _referenced_symbols(tree):
            found.add(_module_dotted(path))
    return found


def _discover_short_session_call_sites() -> set[str]:
    """全仓引用 ``short_db_session`` 的模块（定义处不计，见 ``_referenced_symbols``）。

    被排除的基础设施模块由调用方剔除。
    """
    return _discover_modules_referencing("short_db_session")


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
    """清单必须等于「全仓所有 short_db_session 引用点」减去有意排除的基础设施模块。

    这条交叉核对正是为了防止本文件重演「清单只抄 Task 1 触碰过的文件」而漏站点：
    新增（或漏记）的站点会在这里以清单缺项的形态失败，而不是静默留在网外。
    """
    discovered = _discover_short_session_call_sites() - set(EXCLUDED_INFRA_MODULES)
    expected = set(EXPECTED_SHORT_SESSION_MODULES)

    missing = sorted(discovered - expected)
    stale = sorted(expected - discovered)
    assert not missing, f"以下模块在用 short_db_session 却不在清单里，请补入并说明其 Worker 可达路径：{missing}"
    assert not stale, f"清单里以下模块已不再调用 short_db_session，请移除或说明原因：{stale}"


def test_only_registered_modules_may_touch_the_global_session() -> None:
    """「谁可以碰全局会话」必须是显式登记的决定，不能靠惯例。

    覆盖的正是最危险的回归形态：新增一个直接 ``async with AsyncSessionLocal()`` 的模块。
    只看得见 ``short_db_session(`` 的旧实现对此完全无感（终审 Important-2 实测：加一个这样的
    模块后整套仍 17 passed）；这里要求全仓引用集合恰好等于 allowlist，新模块要么改走
    ``short_db_session``，要么被有意识地登记并接受 loop 安全性审查。
    """
    discovered = _discover_modules_referencing("AsyncSessionLocal")
    allowed = set(EXCLUDED_INFRA_MODULES) | set(EXCLUDED_SINGLE_LOOP_MODULES)

    unregistered = sorted(discovered - allowed)
    stale = sorted(allowed - discovered)
    assert not unregistered, (
        "以下模块引用了全局 AsyncSessionLocal 却未登记。Worker 可达的改用 short_db_session()；"
        "确实只跑在单 loop 进程里的，登记进 EXCLUDED_SINGLE_LOOP_MODULES（或 EXCLUDED_INFRA_MODULES）"
        f"并写明其调用方为何不出现在 Celery 子树内（判据见 spec §10.4）：{unregistered}"
    )
    assert not stale, f"allowlist 里以下模块已不再引用 AsyncSessionLocal，请移除或说明原因：{stale}"


def test_ast_discovery_ignores_comments_and_strings() -> None:
    """注释/字符串里的同名文本不得算作引用。

    回归锚点：正则实现会把 ``sync.py`` 里一句含 ``short_db_session()`` 的注释判成新站点，
    于是**改文档就会 CI 红**。AST 必须对纯文本免疫。
    """
    tree = ast.parse(
        '"""docstring 提及 short_db_session( 与 AsyncSessionLocal。"""\n'
        "# 备注：异步路径请改用 short_db_session()，不要直接碰 AsyncSessionLocal\n"
        'TEXT = "short_db_session() / AsyncSessionLocal"\n'
    )
    # 只有赋值目标 ``TEXT`` 是符号；两个会话符号都只作为文本出现在注释/字符串里。
    assert _referenced_symbols(tree) == {"TEXT"}


def test_expected_module_list_is_exactly_the_worker_sites() -> None:
    """清单互斥且计数明确：防止顺手把单 loop 站点拉进来，或漏掉多轮加入的站点。"""
    assert len(EXPECTED_SHORT_SESSION_MODULES) == 13
    assert len(set(EXPECTED_SHORT_SESSION_MODULES)) == 13
    # allowlist 各段的规模也钉住：扩清单必须是有意识的动作，不能顺手加进去。
    assert len(EXCLUDED_INFRA_MODULES) == 2
    assert len(EXCLUDED_SINGLE_LOOP_MODULES) == 5
    excluded = set(EXCLUDED_SINGLE_LOOP_MODULES) | set(EXCLUDED_INFRA_MODULES)
    assert excluded.isdisjoint(EXPECTED_SHORT_SESSION_MODULES)
