# B-2d 实施计划：deepagents 编排契约反依赖收敛（schemas/constants 中立化）

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/deepagents/{orchestrator,runner,subagent_graphs}.py` 对 `tenant.agents.{schemas,constants}` 的运行期 import——把 deepagents 使用的 agent 域枚举/常量下沉到中立 `models` 域、把对话 DTO 依赖收敛为「L3 包内中性契约 + L1 装配适配」。

**Architecture:** 延续 B-1/B-2 的 **契约中立化 + 边界适配** 范式：

- **枚举/常量下沉**：`AgentPlanner`/`AgentRuntimeMode`/`SubAgentRoleHint` 及其派生常量（`SUB_AGENT_ROLE_HINTS/DISPLAY/LABELS`）是 agent 域配置取值的纯描述，与 `models/agent/agent.py` 已承载的 `AgentStatus`/`AgentType` 同类——整体迁入新中立模块 `models/agent/constants.py`；`tenant/agents/constants.py` 变 re-export 薄壳，L1 引用方（`agents/meta.py`、`a2a/services/host_bindings.py`、`services/sub_agents.py`）零改动。`langgraph/runner.py`（同属 L3、同符号）一并切换，清掉该枚举在 L3 的最后一个反依赖。
- **L3 中性 DTO**：deepagents 运行期只读父请求 `query/inputs/conversation_id`、只产出 `answer+steps`——定义 L3 包内 dataclass `ParentChatInput`/`SubAgentPlanResult`（`deepagents/io.py`）；不再 import `ChatRequest`/`ChatResponse`。
- **L1 窄入口**：`AgentService` 增 `chat_as_child_simple(child_id, *, query, inputs)`（内部构造 `ChatRequest` 调既有 `chat_as_child`），deepagents 免构造子任务请求。
- **L1 边界适配**：唯一调用方 `chat_entry.py` 构造 `ParentChatInput`、把返回的 `SubAgentPlanResult` 包回 `ChatResponse`（`answer`/`sources=[]`/`steps`），下游 `maybe_augment_a2a`/`_complete_chat_turn` 不变。

**Tech Stack:** FastAPI / SQLAlchemy async / LangGraph / deepagents(optional)（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`integrations`（L3）禁止运行期 import `tenant`（L1）；`TYPE_CHECKING` 下的类型注解 import 允许（B-1 后既有状态：`deepagents` 三文件 `if TYPE_CHECKING: from app.tenant.agents.services.agent import AgentService` 保留不动）；L3 与 `tenant` 均允许依赖 `models` 域（既有事实：deepagents 已 `from app.models.agent import ...`）。本计划完成后 `app/integrations/deepagents/*.py` 与 `app/integrations/langgraph/runner.py` 内不得再出现运行期（顶层或函数级、非 TYPE_CHECKING 块）的 `from app.tenant.agents.{schemas,constants}` import。
- 语义保持：子智能体聊天请求构成（query + 父 inputs）、planner `engine` 值（deepagents/platform 字符串）、`steps` 轨迹结构、返回给 L1 的 `ChatResponse(answer, sources=[], steps)`、A2A 增强与 `_complete_chat_turn` 行为均零变化。
- 中文 docstring：新增/改动模块须写模块与公开方法 docstring。
- 体量：改动文件不得超过 500 行；单文件 ≥400 行新增逻辑优先拆文件。
- 测试：每任务跑指定 pytest + 全量回归（`uv run python -m pytest -q`，当前 main 基线 **445 passed**；机器上 `uv run pytest -q` 收集失败，须用 `python -m pytest`）；收尾不得少于基线。
- 提交：每任务单独 commit，message 简体中文 `<type>(<scope>): <简述>`（本系列统一 `engine` scope）。

---

### Task 1: agent 域枚举/常量下沉 `models/agent/constants.py`（L3 import 切换）

**Files:**
- Create: `backend/app/models/agent/constants.py`
- Modify: `backend/app/tenant/agents/constants.py`
- Modify: `backend/app/integrations/deepagents/orchestrator.py`
- Modify: `backend/app/integrations/deepagents/runner.py`
- Modify: `backend/app/integrations/deepagents/subagent_graphs.py`
- Modify: `backend/app/integrations/langgraph/runner.py`

**Interfaces:**
- Consumes: 无（纯搬移）。
- Produces（供 Task 3 等后续直接消费，名称与既有完全一致）:
  - `models.agent.constants.{AgentRuntimeMode, AgentPlanner, SubAgentRoleHint, SUB_AGENT_ROLE_HINTS, SUB_AGENT_ROLE_DISPLAY, SUB_AGENT_ROLE_LABELS}`
  - `tenant.agents.constants` 变 re-export（L1 引用方 import 路径不变）。

- [ ] **Step 1: 记录基线引用面**

Run（backend/ 下）：
```bash
rg -ln "from app.tenant.agents.constants import|from app.tenant.agents import constants|tenant\.agents\.constants" app/
uv run python -m pytest -q | tail -1
```
Expected：引用方恰为 7 处——`integrations/deepagents/{orchestrator,runner,subagent_graphs}.py`、`integrations/langgraph/runner.py`、`tenant/a2a/services/host_bindings.py`、`tenant/agents/meta.py`、`tenant/agents/services/sub_agents.py`；测试条数 445。

- [ ] **Step 2: 新建中立模块**

新建 `backend/app/models/agent/constants.py`，内容为 `tenant/agents/constants.py` 的**逐字迁移**，模块 docstring 改写为：

```python
"""智能体运行时配置枚举/常量（中立域，L3/tenant 共用）。

``agent.config`` 键取值与子智能体 role_hint 的纯描述，供校验、meta、编排与
``integrations/deepagents``/``langgraph`` 适配层共用；L1 侧经
``tenant.agents.constants`` re-export（路径稳定）。

- ``AgentRuntimeMode``：``config.runtime_mode``
- ``AgentPlanner``：``config.planner``
- ``SubAgentRoleHint`` / ``SUB_AGENT_ROLE_*``：子智能体 ``role_hint`` 校验与展示
"""

import enum


class AgentRuntimeMode(str, enum.Enum):
    """``agent.config.runtime_mode``：RAG 与编排路径开关。"""

    LEGACY = "legacy"
    AUTONOMOUS = "autonomous"
    WORKFLOW = "workflow"


class AgentPlanner(str, enum.Enum):
    """``agent.config.planner``：子智能体 / A2A 宿主编排引擎。"""

    DEEPAGENTS = "deepagents"
    PLATFORM = "platform"
    A2A_ORCHESTRATOR = "a2a_orchestrator"


class SubAgentRoleHint(str, enum.Enum):
    RETRIEVAL = "retrieval"
    OCR = "ocr"
    SUMMARY = "summary"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


SUB_AGENT_ROLE_HINTS = frozenset(h.value for h in SubAgentRoleHint)

# value -> (label, hint)
SUB_AGENT_ROLE_DISPLAY: dict[str, tuple[str, str | None]] = {
    SubAgentRoleHint.RETRIEVAL.value: ("检索", "知识检索"),
    SubAgentRoleHint.OCR.value: ("OCR", "OCR 识别"),
    SubAgentRoleHint.SUMMARY.value: ("总结", "摘要归纳"),
    SubAgentRoleHint.COMPLIANCE.value: ("合规", "合规审查"),
    SubAgentRoleHint.CUSTOM.value: ("自定义", "自定义"),
}

# DeepAgents 子智能体描述（优先 hint 长文案）
SUB_AGENT_ROLE_LABELS: dict[str, str] = {role: (hint or label) for role, (label, hint) in SUB_AGENT_ROLE_DISPLAY.items()}
```

- [ ] **Step 3: `tenant/agents/constants.py` 改 re-export 薄壳**

全文替换为：

```python
"""智能体 runtime_mode / planner 与子智能体 role_hint 枚举（re-export）。

定义已下沉中立域 ``app.models.agent.constants``；本模块保持既有引用路径
（``agents/meta.py``、``a2a/services/host_bindings.py``、``services/sub_agents.py`` 等 L1 内部），
禁止再在 L3/新代码 import 本模块——L3 应指向 ``app.models.agent.constants``。
"""

from app.models.agent.constants import (
    SUB_AGENT_ROLE_DISPLAY,
    SUB_AGENT_ROLE_HINTS,
    SUB_AGENT_ROLE_LABELS,
    AgentPlanner,
    AgentRuntimeMode,
    SubAgentRoleHint,
)

__all__ = [
    "AgentRuntimeMode",
    "AgentPlanner",
    "SubAgentRoleHint",
    "SUB_AGENT_ROLE_HINTS",
    "SUB_AGENT_ROLE_DISPLAY",
    "SUB_AGENT_ROLE_LABELS",
]
```

- [ ] **Step 4: L3 四处 import 切换到 models**

`deepagents/orchestrator.py`（现 L26）：

```python
from app.models.agent.constants import AgentPlanner
```

`deepagents/runner.py`（现 L22）：

```python
from app.models.agent.constants import AgentPlanner
```

`deepagents/subagent_graphs.py`（现 L21）：

```python
from app.models.agent.constants import SUB_AGENT_ROLE_HINTS, SUB_AGENT_ROLE_LABELS
```

`integrations/langgraph/runner.py`（现 L33）：

```python
from app.models.agent.constants import AgentRuntimeMode
```

（import 须按 isort 字母序落入 models 组。）

- [ ] **Step 5: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/models/agent/constants.py app/tenant/agents/constants.py app/integrations/deepagents app/integrations/langgraph/runner.py app/tenant/a2a/services/host_bindings.py app/tenant/agents/meta.py app/tenant/agents/services/sub_agents.py
rg -n "from app.tenant.agents.constants|from app.tenant.agents import constants" app/integrations || echo "L3 对 tenant.agents.constants 引用清零"
uv run python -m pytest tests/tenant/agents/test_deepagents_orchestrator.py tests/flow/test_langgraph_rag.py -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；rg 无命中；定向与全量测试均 445 passed 不变（L1 引用方经 re-export 行为不变）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/agent/constants.py backend/app/tenant/agents/constants.py backend/app/integrations/deepagents/orchestrator.py backend/app/integrations/deepagents/runner.py backend/app/integrations/deepagents/subagent_graphs.py backend/app/integrations/langgraph/runner.py
git commit -m "refactor(engine): agent 域枚举常量下沉 models.agent.constants

deepagents 与 langgraph/runner 属 L3，不应 import tenant.agents.constants；
枚举迁中立 models 域后 tenant 路径改 re-export，L1 引用零改动。"
```

---

### Task 2: L1 窄方法 `chat_as_child_simple` + L3 中性 DTO（TDD）

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_entry.py`
- Create: `backend/app/integrations/deepagents/io.py`
- Test: `backend/tests/tenant/agents/test_chat_as_child_simple.py`（新建）

**Interfaces:**
- Consumes: 无（`ChatRequest`/`ChatResponse` 为 L1 既有 schema）。
- Produces（供 Task 3 使用）:
  - `AgentService.chat_as_child_simple(self, child_id: UUID, *, query: str, inputs: dict | None = None) -> ChatResponse`
  - `deepagents.io.ParentChatInput(query: str, inputs: dict = field(default_factory=dict), conversation_id: str | None = None)`
  - `deepagents.io.SubAgentPlanResult(answer: str, steps: list[dict] = field(default_factory=list))`

- [ ] **Step 1: 先写失败测试**

新建 `backend/tests/tenant/agents/test_chat_as_child_simple.py`：

```python
"""chat_as_child_simple 委托 chat_as_child 并构造子任务 ChatRequest（L3 deepagents 契约用）。"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse


def _run(coro):
    return asyncio.run(coro)


class _ChildEntry(SimpleNamespace):
    """最小替身：仅承载被委托的 chat_as_child，记录入参。"""

    async def chat_as_child(self, child_id, body: ChatRequest) -> ChatResponse:
        self.calls.append((child_id, body))
        return ChatResponse(answer="child-ok")


def test_chat_as_child_simple_builds_chat_request():
    from app.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

    entry = _ChildEntry()
    entry.calls = []
    bound = AgentChatEntryMixin.chat_as_child_simple.__get__(entry, type(entry))
    child_id = uuid4()
    resp = _run(bound(child_id, query="q", inputs={"k": "v"}))

    assert resp.answer == "child-ok"
    (got_child, body) = entry.calls[0]
    assert got_child == child_id
    assert isinstance(body, ChatRequest)
    assert body.query == "q"
    assert body.inputs == {"k": "v"}


def test_chat_as_child_simple_defaults_inputs_empty():
    from app.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

    entry = _ChildEntry()
    entry.calls = []
    bound = AgentChatEntryMixin.chat_as_child_simple.__get__(entry, type(entry))
    _run(bound(uuid4(), query="hi"))
    (_child, body) = entry.calls[0]
    assert body.inputs == {}
```

- [ ] **Step 2: 运行确认失败**

Run（backend/ 下）：`uv run python -m pytest tests/tenant/agents/test_chat_as_child_simple.py -q`
Expected：FAIL——`AttributeError: type object 'AgentChatEntryMixin' has no attribute 'chat_as_child_simple'`。

- [ ] **Step 3: 实现窄方法与中性契约**

`chat_entry.py` 在 `chat_as_child`（现 L198）定义之前插入：

```python
    async def chat_as_child_simple(
        self,
        child_id: UUID,
        *,
        query: str,
        inputs: dict | None = None,
    ) -> ChatResponse:
        """子智能体工位简化入口：免构造 ``ChatRequest``（供 L3 deepagents 契约调用）。"""
        return await self.chat_as_child(
            child_id,
            ChatRequest(query=query, inputs=inputs or {}),
        )
```

新建 `backend/app/integrations/deepagents/io.py`：

```python
"""DeepAgents 适配层中性契约（L3，不依赖 tenant 域）。

``ParentChatInput``：父对话输入（L1 ``chat_entry`` 从 ``ChatRequest`` 解包构造）；
``SubAgentPlanResult``：子智能体编排结果（L1 ``chat_entry`` 包回 ``ChatResponse``）。
供 ``orchestrator``/``runner``/``subagent_graphs`` 与 L1 装配点共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParentChatInput:
    """父对话输入的 L3 最小视图：query / inputs / conversation_id。"""

    query: str
    inputs: dict = field(default_factory=dict)
    conversation_id: str | None = None


@dataclass
class SubAgentPlanResult:
    """子智能体编排结果：最终回答与 steps 轨迹（L1 侧转 ``ChatResponse``）。"""

    answer: str
    steps: list[dict] = field(default_factory=list)
```

- [ ] **Step 4: 运行确认通过**

Run（backend/ 下）：
```bash
uv run python -m pytest tests/tenant/agents/test_chat_as_child_simple.py -q
uv run ruff check app/tenant/agents/services/agent/chat_entry.py app/integrations/deepagents/io.py
```
Expected：2 passed；ruff 全绿。

- [ ] **Step 5: Commit**

```bash
git add backend/app/tenant/agents/services/agent/chat_entry.py backend/app/integrations/deepagents/io.py backend/tests/tenant/agents/test_chat_as_child_simple.py
git commit -m "refactor(engine): AgentService 增 chat_as_child_simple 窄入口与 deepagents 中性 DTO

子智能体工位调用免构造 ChatRequest；ParentChatInput/SubAgentPlanResult
成为 L3 deepagents 与 L1 chat_entry 间的中立契约。"
```

---

### Task 3: deepagents 三文件 DTO 中性化 + `chat_entry` 边界适配

**Files:**
- Modify: `backend/app/integrations/deepagents/orchestrator.py`
- Modify: `backend/app/integrations/deepagents/runner.py`
- Modify: `backend/app/integrations/deepagents/subagent_graphs.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_entry.py`

**Interfaces:**
- Consumes: Task 1 `models.agent.constants`、Task 2 `chat_as_child_simple`/`deepagents.io.*`。
- Produces: 收敛终态——`integrations/deepagents/*.py` 不再运行期 import `tenant.agents.schemas`；顶层入口 `run_subagent_planned_chat(svc, parent, bindings, body: ParentChatInput) -> SubAgentPlanResult` 与 `run_deepagents_chat(svc, parent, bindings, body: ParentChatInput) -> SubAgentPlanResult`（仍从 `app.integrations.deepagents.orchestrator` 导入）。

- [ ] **Step 1: 前置确认唯一 L1 调用方**

Run（backend/ 下）：
```bash
rg -n "run_subagent_planned_chat|run_deepagents_chat|_make_child_node|build_compiled_subagents" app/ | rg -v "deepagents/(orchestrator|runner|subagent_graphs|__init__)\.py"
```
Expected：`deepagents/__init__.py`（re-export）+ `tenant/agents/services/agent/chat_entry.py:98-101`（唯一 L1 调用）。

- [ ] **Step 2: `subagent_graphs.py`**

- 移除顶层 `from app.tenant.agents.schemas.agent import ChatRequest`（现 L22）。
- `_make_child_node` 内子任务调用（现 L73-76）改为窄入口：

```python
        resp = await svc.chat_as_child_simple(
            child_id,
            query=query or "请根据上下文完成任务",
        )
```

- 保留 `if TYPE_CHECKING: from app.tenant.agents.services.agent import AgentService`（类型注解）。

- [ ] **Step 3: `runner.py`**

- 移除顶层 `from app.tenant.agents.constants import AgentPlanner`（Task 1 已改 models，确认现状为 `from app.models.agent.constants import AgentPlanner`）与 `from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse`（现 L23）；新增：

```python
from app.integrations.deepagents.io import ParentChatInput, SubAgentPlanResult
```

- `_thread_id`（现 L40）签名与 docstring：

```python
def _thread_id(parent: Agent, body: ParentChatInput) -> str:
    """DeepAgents checkpointer 线程 id。"""
```

- `run_deepagents_chat`（现 L101）签名与返回：

```python
async def run_deepagents_chat(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ParentChatInput,
) -> SubAgentPlanResult:
    """
    DeepAgents 主循环：主模型通过 ``task`` 工具委派 ``CompiledSubAgent``。

    ``body`` 为 L1 ``chat_entry`` 从 ``ChatRequest`` 解包的中性输入；
    返回 ``SubAgentPlanResult``，由 L1 包回 ``ChatResponse``。

    ``recursion_limit`` 来自 ``config.max_plan_iterations``（默认 12）。
    """
```

- 函数体末两处 `ChatResponse` 构造（现 L165 等，全函数仅一处 `return ChatResponse(answer=answer, sources=[], steps=steps)`）改为：

```python
    return SubAgentPlanResult(answer=answer, steps=steps)
```

- 保留 `if TYPE_CHECKING: from app.tenant.agents.services.agent import AgentService`。

- [ ] **Step 4: `orchestrator.py`**

- 移除顶层 `from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse`（现 L25）；确认 `AgentPlanner` 来自 `app.models.agent.constants`（Task 1）。新增：

```python
from app.integrations.deepagents.io import ParentChatInput, SubAgentPlanResult
```

- `_run_platform_planned`（现 L109）签名与 docstring：

```python
async def _run_platform_planned(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ParentChatInput,
) -> SubAgentPlanResult:
    """按规划依次 chat_as_child，最后主模型综合子回答。"""
```

- 函数内子任务调用（现 L137）：

```python
        child_resp = await svc.chat_as_child_simple(
            UUID(sid),
            query=task,
            inputs=body.inputs,
        )
```

- 函数内两处 `ChatResponse(...)` 构造（现 L165-169 无 sub_answers 分支、L185 综合返回）均改 `SubAgentPlanResult(...)`（`sources=[]` 参数删除，仅 `answer=`/`steps=`）：

```python
    if not sub_answers:
        return SubAgentPlanResult(
            answer="未能委派子智能体完成任务，请检查绑定与模型配置。",
            steps=steps,
        )
```

```python
    return SubAgentPlanResult(answer=final, steps=steps)
```

- `run_subagent_planned_chat`（现 L201）签名与 docstring：

```python
async def run_subagent_planned_chat(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ParentChatInput,
) -> SubAgentPlanResult:
    """有子智能体绑定时，由 DeepAgents 或平台规划器拆解并委派子智能体。"""
```

- 函数体不变（`resp.steps = steps + resp.steps` 对 dataclass 同样成立）。

- 保留 `if TYPE_CHECKING: from app.tenant.agents.services.agent import AgentService`。

- [ ] **Step 5: `chat_entry.py` L1 边界适配**

- `chat` 主流程子智能体分支（现 L98-101）改为解包 + 包回：

```python
            if bindings:
                from app.integrations.deepagents.io import ParentChatInput
                from app.integrations.deepagents.orchestrator import run_subagent_planned_chat

                route = "subagent"
                result = await run_subagent_planned_chat(
                    self,
                    agent,
                    bindings,
                    ParentChatInput(
                        query=chat_body.query,
                        inputs=chat_body.inputs,
                        conversation_id=chat_body.conversation_id,
                    ),
                )
                response = ChatResponse(answer=result.answer, sources=[], steps=result.steps)
```

（`ChatRequest`/`ChatResponse` 已在 chat_entry 顶层 import，保持不变。）

- [ ] **Step 6: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/integrations/deepagents app/tenant/agents/services/agent/chat_entry.py
rg -n "from app\.tenant\.agents\.schemas|from app\.tenant\.agents\.constants" app/integrations/deepagents app/integrations/langgraph || echo "L3 deepagents/langgraph 对 tenant.agents schemas/constants 运行期引用清零"
uv run python -m pytest tests/tenant/agents/test_deepagents_orchestrator.py tests/tenant/agents/test_chat_as_child_simple.py tests/flow/test_langgraph_rag.py -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；rg 无命中（TYPE_CHECKING 块内 `from app.tenant.agents.services.agent import AgentService` 允许，不匹配此 pattern）；定向测试通过；全量 445 passed 不变。

- [ ] **Step 7: Commit**

```bash
git add backend/app/integrations/deepagents/orchestrator.py backend/app/integrations/deepagents/runner.py backend/app/integrations/deepagents/subagent_graphs.py backend/app/tenant/agents/services/agent/chat_entry.py
git commit -m "refactor(engine): deepagents 三文件改用中性契约并收口 L1 边界适配

运行期不再 import tenant.agents.schemas；子任务经 chat_as_child_simple，
顶层输入/输出换 ParentChatInput/SubAgentPlanResult，chat_entry 负责解包与包回。"
```

---

### Task 4: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + 定向 rg 终审**

Run（backend/ 下）：
```bash
uv run ruff check app/integrations/deepagents app/integrations/langgraph/runner.py app/models/agent/constants.py app/tenant/agents
rg -n "from app\.tenant\.agents\.(schemas|constants)|from app\.tenant import agents" app/integrations || echo "integrations 对 tenant.agents schemas/constants 运行期引用清零"
rg -n "from app\.tenant\.agents\.constants|from app\.tenant\.agents import constants" app/tenant || echo "tenant 内仍经 re-export 引用（合法）"
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；第一条 rg 无命中（TYPE_CHECKING `services.agent` 注解允许）；第二条 rg 命中 `agents/meta.py`、`a2a/services/host_bindings.py`、`services/sub_agents.py`（L1 内部 re-export 引用，合法）；pytest ≥ 445。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：
- 在 L105（B-2c 收敛记录）之后追加：

```markdown
> **收敛记录（2026-09-09，B-2d）**：deepagents 编排契约反依赖收敛——`AgentPlanner`/`AgentRuntimeMode`/`SubAgentRoleHint` 及 `SUB_AGENT_ROLE_*` 常量下沉中立域 `models/agent/constants.py`（`tenant.agents.constants` 改 re-export），`integrations/deepagents` 与 `langgraph/runner` 不再运行期 import `tenant.agents.constants`；deepagents 对话 DTO 依赖收口为 L3 中性契约 `deepagents/io.py`（`ParentChatInput`/`SubAgentPlanResult`）+ `AgentService.chat_as_child_simple` 窄入口 + L1 `chat_entry` 边界解包/包回，`orchestrator`/`runner`/`subagent_graphs` 不再运行期 import `tenant.agents.schemas`（TYPE_CHECKING `AgentService` 注解保留）（见 plan [`2026-09-09-engine-di-deepagents-contract`](../plans/2026-09-09-engine-di-deepagents-contract.md)）。
```

- §8 修订记录表追加一行：

```markdown
| 2026-09-09 | B-2d：agent 域枚举下沉 `models.agent.constants`，deepagents 契约收敛——`ParentChatInput`/`SubAgentPlanResult` 中性 DTO + `chat_as_child_simple` 窄入口，deepagents/`langgraph/runner` 对 `tenant.agents.{schemas,constants}` 运行期引用清零 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 B-2d deepagents 编排契约收敛"
```

---

## Self-Review

- **Spec coverage**：目标（deepagents 三文件对 `tenant.agents.{schemas,constants}` 运行期反依赖清零）由 Task 1（常量下沉 + langgraph/runner 顺带）、Task 2（中性 DTO + L1 窄方法）、Task 3（三文件切换 + chat_entry 适配）达成；Task 4 文档终审闭环。`TYPE_CHECKING` `AgentService` 注解按 B-1 既有状态保留（约束中明示允许），不改动。
- **Placeholder scan**：每个 Step 均含完整代码或精确 diff 指引（import 行号、函数签名替换、构造改法）；`runner.py`/`orchestrator.py` 函数体内 `body.query`/`steps` 等引用因输入/输出 dataclass 字段名与 `ChatRequest`/`ChatResponse` 一致而零改动，Task 3 已明示「函数体不变」的边界。
- **Type consistency**：Task 2 定义的 `chat_as_child_simple(child_id, *, query, inputs=None) -> ChatResponse` 与 `io.ParentChatInput(query, inputs=field(default_factory=dict), conversation_id=None)`、`io.SubAgentPlanResult(answer, steps=field(default_factory=list))` 在 Task 3 各处一致引用；顶层入口签名变化唯一消费方为 chat_entry（Step 1 已 rg 确认）；`resp.steps = steps + resp.steps` 对 `SubAgentPlanResult.steps`（list）与 `ChatResponse.steps`（list）行为一致。
