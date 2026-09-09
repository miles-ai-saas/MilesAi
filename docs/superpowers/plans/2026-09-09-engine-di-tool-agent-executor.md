# F2c-B 实施计划：agent 对话工具执行/确认面收敛——L3 中性契约 + L1 executor 注入

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/langchain/tool_agent/loop.py`（L3）对 `tenant.tools.confirmation`（`resolve_tool_meta`/`ToolConfirmationRequired`）与 `tenant.tools.invoke`（`invoke_tool_with_context`）的运行期 import——执行/确认经 L3 中性契约（`tool_agent/tool_contract.py`）+ L1 executor（`tenant/tools/services/agent_executor.py`）注入 `run_tool_calling_chat`。这是 tools 契约计划（F2）最终收尾：`loop.py` 对 `tenant.*` import **清零**。

**完成标准：**
- `loop.py` 内 `from app.tenant.tools` 清零（全 `tenant` import 清零）。
- `run_tool_calling_chat` 增关键字参数 `tool_executor`（L1 chat_rag 装配注入）。
- 行为等价：meta 解析语义（含 BadRequestError/工具不存在文案）、确认门槛（`meta["require_confirmation"]`）、确认信号 → `PendingToolCall`、invoke `confirmed` 双态、输出结构全保留。
- 全量测试 ≥ 461，回归无行为变化。

## 背景事实（已审计）

- `loop.py` 对 `tenant.tools` 的引用（当前全部 8 处调用 + 2 import 行）：
  1. L34-35 imports：`ToolConfirmationRequired, resolve_tool_meta`（confirmation）与 `invoke_tool_with_context`（invoke）。
  2. L87 confirm 分支：`invoke_tool_with_context(db, ctx, slug, confirm_params, confirmed=True, agent_id=agent_id, actor_user_id=ctx.user_id, invoke_source="agent")` → 异常兜底（except Exception 转错误响应）。
  3. L169/175 模拟提取自救：`resolve_tool_meta(db, ctx, slug)`（except Exception → meta=None）→ `if meta and not meta.get("require_confirmation")` → `invoke_tool_with_context(..., confirmed=True, ...)`。
  4. L228/233 意图兜底（image_tool）：同 3。
  5. L339 主循环：`resolve_tool_meta(db, ctx, slug)`（except BadRequestError → 工具不存在长文案；except Exception → raise）。
  6. L366-377 `if meta["require_confirmation"]:` → `invoke_tool_with_context(..., confirmed=False, ...)`；`except ToolConfirmationRequired as exc:` → `PendingToolCall(slug=exc.slug, name=exc.tool_name, description=exc.tool_description, params=exc.params)`。
  7. L399-409 `invoke_tool_with_context(..., confirmed=True, ...)`；`except ToolConfirmationRequired: raise` / `except BadRequestError → 错误响应`。
- meta 消费为 **dict 语义**：`meta["require_confirmation"]`、`meta.get(...)`、`meta and not meta.get(...)`、`meta` 为 None 的 `if meta and` 判断——中性契约应保留 dict 语法以最小化 loop diff。
- `run_tool_calling_chat` 唯一调用者 = `chat_rag.py` 两分支（L231-243/L265-281，均已有 F2b 装配 `assemble_agent_tools` 注入 `platform_tools`）；chat_rag 两处均持有 `self.db`/`self.ctx`/`agent_id`（方法参数）。
- loop 仍需 `db`/`ctx` 形参（media resolve L129 `resolve_media_refs` 等）——保留，不删。
- `ToolConfirmationRequired` 字段：`slug`/`tool_name`/`tool_description`/`params`；`PendingToolCall`（`models/agent/chat_io.py`）字段：`slug`/`name`/`description`/`params`（loop 现手动映射）。`ToolConfirmationRequired` 继承 `BadRequestError`（`common.exceptions`，L3 可继续 import `BadRequestError`）。
- 直接单测文件不存在；间接回归罩：`tests/tenant/generative/test_generative_{image,video}.py`（loop 链路）、`tests/tenant/tools/test_tools_confirmation.py`（确认策略面）。

**Architecture:**

- **L3 中性契约**（新建 `integrations/langchain/tool_agent/tool_contract.py`）：
  ```python
  """agent 对话工具执行/确认契约（L3 中性，L1 适配实现注入）。

  ``loop.py`` 只依赖本契约：meta 解析返回 dict（键 ``slug``/``name``/``description``/
  ``require_confirmation``/``source``/``tool_id``）；invoke 需确认时抛 ``ToolConfirmationSignal``
  （字段与 ``tenant.tools.confirmation.ToolConfirmationRequired`` 同名同构）。
  """

  from __future__ import annotations

  from typing import Any, Protocol
  from uuid import UUID

  from app.models.agent.chat_io import PendingToolCall  # noqa: F401  # 契约文档性 re-export（如不需要可删）

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
  ```
  > 若 `PendingToolCall` re-export 无消费方（loop 已从 `models.agent.chat_io` 直接 import），删除该 import 行——以 ruff 无 unused 为准。
- **L1 executor**（新建 `tenant/tools/services/agent_executor.py`）：`AgentToolExecutor`（构造收 db/ctx/agent_id/actor_user_id/invoke_source）实现 `meta`（委托 `resolve_tool_meta`，返回原 dict）/`invoke`（委托 `invoke_tool_with_context`，捕获 `ToolConfirmationRequired` → `raise ToolConfirmationSignal(exc.slug, exc.tool_name, exc.tool_description, exc.params) from None`）；`build_agent_tool_executor(...)` 工厂（chat_rag 消费）。契约类 import 自 L3（L1→L3 合法）。
- **loop 改造**：删 2 import 行；签名加 `tool_executor: "ToolExecutor"`；8 处调用按「背景事实」映射表改走 executor 方法（meta 调用只替换调用源保留 dict 消费语法；invoke 调用删 db/ctx/agent_id/actor_user_id/invoke_source 实参——均由 executor 捕获）；`except ToolConfirmationRequired` ×2 → `except ToolConfirmationSignal`。
- **chat_rag 接线**：两调用点各在 `platform_tools=...` 之前加 `tool_executor = build_agent_tool_executor(self.db, self.ctx, agent_id=agent_id, actor_user_id=self.ctx.user_id, invoke_source="agent")`，传 `tool_executor=tool_executor,`（函数级 import）。

## Global Constraints

- 分层：改后 `loop.py` 对 `tenant.*` import 清零（L3 允许 `common.exceptions`/`models.agent.chat_io`/L3 内契约）；`agent_executor.py` 为 L1（import L3 `tool_contract` 契约类 + 本域 `tenant.tools.{confirmation,invoke}` + `core.tenant`——全部合法向下/同域）；新增 import 均向下，禁止反向。
- **行为等价**：`confirmed` 双态、meta dict 键、`BadRequestError`「工具不存在」路径、确认异常字段名（`slug`/`tool_name`/`tool_description`/`params`）、PendingToolCall 组装、错误响应文案全保留。
- 中文 docstring；改动 ≤ 500 行。
- 每任务定向 + 全量回归（基线 **461 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: L3 中性契约 `tool_agent/tool_contract.py`

**Files:**
- Create: `backend/app/integrations/langchain/tool_agent/tool_contract.py`

**Interfaces:**
- Produces: `ToolConfirmationSignal`/`ToolExecutor`（Task 2/3 消费，签名见「Architecture」verbatim）。
- Consumes: 无。

- [ ] **Step 1: 实现**

按「Architecture」verbatim 建模块。若 `PendingToolCall` re-export 行无实际消费方则删（loop 直接 `from app.models.agent.chat_io import PendingToolCall` 已存在），模块仅含信号 + Protocol。

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/integrations/langchain/tool_agent/tool_contract.py
uv run python -c "import app.integrations.langchain.tool_agent.tool_contract as m; print(m.ToolConfirmationSignal, m.ToolExecutor)"
```
Expected：ruff 绿；import 成功。

- [ ] **Step 3: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/tool_contract.py
git commit -m "refactor(engine): 新增 agent 对话工具执行/确认中性契约

ToolConfirmationSignal/ToolExecutor 供 loop 消费与 L1 适配实现注入。"
```

---

### Task 2: L1 executor `agent_executor.py` + 定向单测

**Files:**
- Create: `backend/app/tenant/tools/services/agent_executor.py`
- Create: `backend/tests/tenant/tools/test_agent_executor.py`

**Interfaces:**
- Consumes: Task 1 `ToolConfirmationSignal`/`ToolExecutor`（L3）、`resolve_tool_meta`（`tenant.tools.confirmation`）、`invoke_tool_with_context`（`tenant.tools.invoke`）、`TenantContext`（`core.tenant`）。
- Produces: `build_agent_tool_executor(db, ctx, *, agent_id, actor_user_id, invoke_source="agent")`（Task 3 消费）。

- [ ] **Step 1: 实现（代码 verbatim）**

```python
"""agent 对话工具执行器（L1，适配 L3 中性契约）。

``AgentToolExecutor`` 实现 ``tool_agent.tool_contract.ToolExecutor``：meta 委托
``resolve_tool_meta``（dict 原样返回），invoke 委托 ``invoke_tool_with_context``
并把 ``ToolConfirmationRequired`` 转 L3 中性 ``ToolConfirmationSignal``。db/ctx 与
执行上下文（agent_id/actor_user_id/invoke_source）在构造时捕获，供
``tool_agent.loop.run_tool_calling_chat`` 经 ``tool_executor`` 参数注入使用。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invoke import invoke_tool_with_context


class AgentToolExecutor:
    """对话工具执行器：meta 解析 + invoke（确认信号中性转换）。"""

    def __init__(
        self,
        db: AsyncSession,
        ctx: TenantContext,
        *,
        agent_id: UUID | None,
        actor_user_id: UUID | None,
        invoke_source: str = "agent",
    ) -> None:
        self._db = db
        self._ctx = ctx
        self._agent_id = agent_id
        self._actor_user_id = actor_user_id
        self._invoke_source = invoke_source

    async def meta(self, slug: str, *, tool_id: UUID | None = None) -> dict[str, Any]:
        return await resolve_tool_meta(self._db, self._ctx, slug, tool_id=tool_id)

    async def invoke(
        self,
        slug: str,
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        tool_id: UUID | None = None,
    ) -> dict[str, Any]:
        try:
            return await invoke_tool_with_context(
                self._db,
                self._ctx,
                slug,
                params,
                tool_id=tool_id,
                confirmed=confirmed,
                actor_user_id=self._actor_user_id,
                agent_id=self._agent_id,
                invoke_source=self._invoke_source,
            )
        except ToolConfirmationRequired as exc:
            raise ToolConfirmationSignal(
                exc.slug,
                exc.tool_name,
                exc.tool_description,
                exc.params,
            ) from None


def build_agent_tool_executor(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    agent_id: UUID | None,
    actor_user_id: UUID | None,
    invoke_source: str = "agent",
) -> AgentToolExecutor:
    """构造对话工具执行器（chat_rag 装配点注入 loop 用）。"""
    return AgentToolExecutor(
        db,
        ctx,
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        invoke_source=invoke_source,
    )
```

> 核对 `resolve_tool_meta` 现签名：`resolve_tool_meta(db, ctx, slug, *, tool_id=None)`——确认实际带不带 `tool_id` 默认；`invoke_tool_with_context` 参数名与顺序见 `context.py`。实现以现网签名为准微调，不改变行为。

- [ ] **Step 2: 定向单测（TDD）**

`tests/tenant/tools/test_agent_executor.py`：
- 用例 A（meta 委托）：mock `resolve_tool_meta` 返回 dict，断言 executor.meta 原样返回且调用参数正确（可 monkeypatch 模块内 `resolve_tool_meta`）。
- 用例 B（invoke 委托 + confirmed 透传）：monkeypatch `invoke_tool_with_context`（async 假实现记录参数），断言 `db/ctx/slug/params/confirmed/actor_user_id/agent_id/invoke_source="agent"` 均透传。
- 用例 C（信号转换）：`invoke_tool_with_context` raise `ToolConfirmationRequired("calc","计算器",None,{})` → executor.invoke 抛 `ToolConfirmationSignal`，字段 `slug/tool_name/tool_description/params` 一一对应。

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/tools/services/agent_executor.py tests/tenant/tools/test_agent_executor.py
uv run python -m pytest tests/tenant/tools/test_agent_executor.py -q
```
Expected：ruff 绿、3 用例全过。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/tools/services/agent_executor.py backend/tests/tenant/tools/test_agent_executor.py
git commit -m "refactor(engine): agent 对话工具执行器 L1 agent_executor

实现中性 ToolExecutor 契约，确认信号转 L3 ToolConfirmationSignal。"
```

---

### Task 3: `loop.py` 契约化 + `chat_rag.py` 接线

**Files:**
- Modify: `backend/app/integrations/langchain/tool_agent/loop.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`

**Interfaces:**
- Consumes: Task 1 `ToolConfirmationSignal`/`ToolExecutor`（loop import）、Task 2 `build_agent_tool_executor`（chat_rag import）。
- Produces: 收敛终态——`loop.py` 对 `tenant.*` import 清零；`run_tool_calling_chat(..., tool_executor)` 由 chat_rag 注入。

- [ ] **Step 1: `loop.py` 改造**

- import：删 L34-35；加 `from app.integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal, ToolExecutor`（`tool_contract` 同包）。
- 签名：`usage_sink` 后追加 `tool_executor: ToolExecutor,`。
- 替换映射（逐字锚定，语义等价）：
  - L87 confirm 分支：`output = await tool_executor.invoke(body.pending_tool_slug, confirm_params, confirmed=True)`。
  - L169 与 L228：`meta = await tool_executor.meta(slug)` / `meta = await tool_executor.meta(image_tool)`（外层 except Exception → None 保留）。
  - L175 与 L233：`output = await tool_executor.invoke(slug, params, confirmed=True)` / `(image_tool, {"prompt": fallback_query}, confirmed=True)`。
  - L339：`meta = await tool_executor.meta(slug)`（except BadRequestError / except Exception 保留——BadRequestError 由 L1 meta 原样传播）。
  - L366-377：`await tool_executor.invoke(slug, args, confirmed=False)`；`except ToolConfirmationSignal as exc:`（PendingToolCall 组装体不变，字段同名）。
  - L399-409：`output = await tool_executor.invoke(slug, args, confirmed=True)`；`except ToolConfirmationSignal: raise` / `except BadRequestError` 保留。
- 模块 docstring / 函数 docstring：`invoke_tool_with_context` 相关流程描述改指 `tool_executor`（L1 注入）；确认异常名同步。
- 核对 `db`/`ctx` 是否仍有使用（media resolve 等），未使用则连形参一并清（预期仍使用，保留）。

- [ ] **Step 2: `chat_rag.py` 接线**

两处 `run_tool_calling_chat(...)` 调用点（L231/L265 分支）：在各自 `platform_tools = await assemble_agent_tools(...)` 附近加：

```python
                tool_executor = build_agent_tool_executor(
                    self.db,
                    self.ctx,
                    agent_id=agent_id,
                    actor_user_id=self.ctx.user_id,
                    invoke_source="agent",
                )
```

实参表加 `tool_executor=tool_executor,`；`build_agent_tool_executor` 用函数级 import（与 `assemble_agent_tools` import 位置一致）。

- [ ] **Step 3: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.tools|from app\.tenant import" app/integrations/langchain/tool_agent/loop.py || echo "loop.py 对 tenant import 清零"
rg -n "invoke_tool_with_context|resolve_tool_meta|ToolConfirmationRequired" app/integrations/langchain/tool_agent/loop.py || echo "loop.py 无 L1 执行面符号"
uv run ruff check app/integrations/langchain/tool_agent/loop.py app/tenant/agents/services/agent/chat_rag.py
uv run python -m pytest -q | tail -1
```
Expected：前两条 rg 零命中；ruff 绿；pytest ≥ 461 passed（**整支全量收口**；含 generative 两测试与 confirmation 测试回归罩）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/loop.py backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "refactor(engine): tool_agent 主循环执行/确认改走注入 executor

loop 增 tool_executor 参数，chat_rag 两分支构造 agent_executor 注入；
loop 对 tenant.* import 清零，tools 契约计划（F2）收尾。"
```

---

### Task 4: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + rg 终审**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/integrations/langchain/tool_agent/ || echo "tool_agent 包对 tenant 引用清零"
uv run ruff check app/integrations/langchain/tool_agent app/tenant/tools/services/agent_executor.py
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中（tool_agent 包现含 artifacts/loop/tool_contract——`models.agent`/`common` 不算 tenant）；ruff 绿；pytest ≥ 461。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：在 F2c-A 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-09，F2c-B）**：agent 对话工具执行/确认面收敛——L3 中性契约 `tool_agent/tool_contract.py`（`ToolConfirmationSignal`/`ToolExecutor`），L1 executor `tenant/tools/services/agent_executor.py::build_agent_tool_executor`（meta 委托 `resolve_tool_meta`；invoke 委托 `invoke_tool_with_context`，确认信号转中性）；`tool_agent/loop.py` 增 `tool_executor` 入参由 chat_rag 两分支注入，`resolve_tool_meta`/`invoke_tool_with_context`/`ToolConfirmationRequired` 运行期引用清零（见 plan [`2026-09-09-engine-di-tool-agent-executor`](../superpowers/plans/2026-09-09-engine-di-tool-agent-executor.md)）。tools 契约计划（F2）完成：schema 面（F2b）+ 画布执行（F2c-A）+ 对话执行（F2c-B）三段收敛，`integrations/langchain/tool_agent` 与 `flow_runtime/nodes/tool_nodes` 对 `tenant.tools` 依赖清零。
```

§8 修订表 F2c-A 行之后追加：

```markdown
| 2026-09-09 | F2c-B：agent 对话工具执行面收敛——L3 `tool_contract` 中性契约 + L1 `agent_executor` 注入 loop，tool_agent 包对 `tenant` 依赖清零，F2 tools 契约计划收尾 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 F2c-B 对话工具执行面收敛与 F2 收尾"
```

---

## Self-Review

- **Spec coverage**：目标（loop 对 tenant import 清零 + executor 注入）由 Task 1（契约）+ Task 2（L1 executor）+ Task 3（loop 改造 + chat_rag 接线）达成；Task 4 文档闭环。
- **行为等价**：meta 返回 dict（loop 消费语法零改动）；确认异常字段名与 PendingToolCall 组装不变；BadRequestError 传播路径（meta 不存在/工具失败文案）不变；confirmed 双态语义保留。
- **依赖方向**：契约在 L3（loop 同层引用）；executor 在 L1（import L3 契约向下合法）；chat_rag（L1）import executor 同层。loop 剩余 import 全部 L3/common/models。
- **中间态**：Task 1/2 为纯新增模块，不破坏既有面；Task 3 一次切换 loop+chat_rag（同 commit 收口，无中间态断裂）。
- **测试罩**：generative ×2 + confirmation 回归罩覆盖 loop 链路；executor 新单测覆盖委托与信号转换。
- **Placeholder scan**：无 TBD；关键新代码 verbatim（实现以现网函数签名为准微调，已注明）。
