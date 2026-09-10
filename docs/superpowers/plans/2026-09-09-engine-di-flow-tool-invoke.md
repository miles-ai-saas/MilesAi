# F2c-A 实施计划：画布 `platform_tool` 节点执行回调注入——L3 不再 import `tenant.tools.invoke`

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/tool_nodes.py`（L3）对 `tenant.tools.invoke.invoke_tool_with_context`、`tenant.core.tenant.TenantContext`（构造迁移）与 `infra.db.AsyncSessionLocal` 的运行期 import——工具执行经 `RunContext` 注入的 L1 回调 `invoke_platform_tool` 完成（与 B-2e 的 `submit_generative_*` 注入同构），节点保持纯调度职责。

**完成标准：**
- `tool_nodes.py` 内 `from app.tenant.tools` 清零；不再 import `AsyncSessionLocal`/`TenantContext`/`uuid`。
- `RunContext` 增 `invoke_platform_tool` 回调字段；两根装配点（`chat_rag.flow_run_context` + `flows/services/flow.py` debug-run）注入；LangGraph compiler（`build.py`/`run.py`）与 subflow `build_child_context` 透传（与 `submit_generative_*` 同构，四改点齐）。
- 画布工具执行行为不变（slug/params 合并、confirmed 语义、输出 `{"output", "tool_slug"}`）。
- 全量测试 ≥ 456，回归无行为变化。

## 背景事实（已审计）

- 画布**整体经 LangGraph 执行**：`flow_runtime/runtime_factory` → `integrations/langgraph/flow_runner.run_flow_graph` → compiler `run_compiled_canvas`（`compiler/run.py`）→ `build_canvas_graph`（`compiler/build.py`）。节点运行时 `RunContext` 由 `build.py` `run_node` 闭包内**从 LangGraph state 重建**（`build.py:65`），故回调必须进 state（`run.py` 初始 dict + `build.py` `_State` TypedDict + 重建处）并经 subflow `build_child_context` 拷贝。
- `tool_nodes.platform_tool(node_data, inputs, ctx)` 现执行：合并 params（`_build_invoke_params` 纯函数保留）→ `_tenant_context_from_run(ctx)` 构造 `TenantContext` → `async with AsyncSessionLocal() as db:` 调 `invoke_tool_with_context(db, tenant_ctx, slug, params, confirmed=..., actor_user_id=..., agent_id=..., invoke_source="flow")`。
- `RunContext` 现有回调先例字段（`types.py`）：`resolve_model`/`usage_sink`/`kb_retrieval`/`resolve_generative_{image,video}`/`submit_generative_{image,video}`——新字段遵循同注释/命名风格，并在注释中加「新建根装配点须注入」提示。
- `tenant/tools/invoke/context.py::invoke_tool_with_context` 是重量级 L1 业务服务（meta+确认策略+生图门槛+Hook+调用日志），**原样保留于 L1**；本计划只把「从 L3 直接调用」改为「L1 回调注入」。

**Architecture:**

- **L3 契约**（`flow_runtime/types.py`）：
  ```python
  # 画布平台工具执行回调（L1 注入；None 表示未装配，platform_tool 节点报错）。
  # 回调内部完成 TenantContext 构造与短会话工具执行。新建画布 RunContext
  # 根装配点须随 resolve_generative_* 一并注入（见 chat_rag/flow debug-run）。
  invoke_platform_tool: Callable[..., Awaitable[Any]] | None = None
  ```
  回调签名（关键字）：`async (slug: str, params: dict, ctx: RunContext, *, confirmed: bool) -> dict`——节点把执行时 ctx 整体传入，回调自行转换 tenant 上下文并开会话。
- **节点瘦身**（`tool_nodes.py`）：`platform_tool` 校验 slug/合并 params 后：
  ```python
  invoker = ctx.invoke_platform_tool
  if invoker is None:
      raise BadRequestError("平台工具执行回调未装配（RunContext.invoke_platform_tool）")
  confirmed = bool(node_data.get("confirmed", True))
  output = await invoker(slug, params, ctx, confirmed=confirmed)
  return {"output": output, "tool_slug": slug}
  ```
  删除 `_tenant_context_from_run` 及 `AsyncSessionLocal`/`TenantContext`/`uuid`/`invoke_tool_with_context` imports；docstring 更新调用链描述。
- **L1 回调工厂**（`tenant/tools/services/flow_invoker.py`）：`build_flow_tool_invoker() -> Callable`，闭包内复刻节点现执行逻辑（构造 tenant ctx → 短会话 → `invoke_tool_with_context(..., invoke_source="flow")`）。新增文件避免污染 `custom_tools.py` 的自定义工具语义。
- **传播/注入**（与 B-2e `submit_generative_*` 逐点同构，四个改点）：
  1. `chat_rag.py` `flow_run_context` 的 `RunContext(...)` 加 `invoke_platform_tool=build_flow_tool_invoker(),`
  2. `flows/services/flow.py` debug-run `RunContext(...)` 同加
  3. `compiler/run.py` `initial` dict 加 `"invoke_platform_tool": ctx.invoke_platform_tool,`
  4. `compiler/build.py`：`_State` TypedDict 加 `invoke_platform_tool: Any`；`run_node` 的 `RunContext(...)` 重建加 `invoke_platform_tool=state.get("invoke_platform_tool"),`
  5. `flow_runtime/subflow/resolve.py` `build_child_context` 的 `RunContext(...)` 加 `invoke_platform_tool=parent_ctx.invoke_platform_tool,  # 平台工具执行回调透传到子流程`

## Global Constraints

- 分层：改后 `tool_nodes.py`（L3）对 `tenant` import 清零（`app.flow_runtime`/`app.common.exceptions` 允许）；`flow_invoker.py` 为 L1（可 import L3 `RunContext` 仅作注解与 infra `AsyncSessionLocal`）；新增 import 均向下，禁止反向。`tool_nodes.py` 允许保留 `from app.common.exceptions import BadRequestError` 与 `from app.flow_runtime.types import RunContext`。
- **行为等价**：`confirmed` 语义、`_build_invoke_params`（含 knowledge_search 默认 kb_id、skill_run_script hits 注入）、输出结构 `{"output","tool_slug"}`、`invoke_source="flow"`、actor_user_id=tenant_ctx.user_id、`agent_id=UUID(ctx.agent_id) if ctx.agent_id else None`、无 user_id 时 `UUID(int=0)`——全部迁移进 L1 回调，不得漂移。
- 中文 docstring；改动文件 ≤ 500 行。
- 每任务定向 + 全量回归（基线 **456 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: `RunContext` 回调字段 + `tool_nodes.py` 瘦身

**Files:**
- Modify: `backend/app/flow_runtime/types.py`、`backend/app/flow_runtime/nodes/tool_nodes.py`

**Interfaces:**
- Produces: `RunContext.invoke_platform_tool` 字段（后续 Task 消费，签名与注释见上）。
- Consumes: 无前序接口（本分支起点）。

- [ ] **Step 1: `types.py` 加字段**

在 `submit_generative_video` 之后追加（注释 verbatim 见「Architecture」）。import 无需新增（`Callable`/`Awaitable`/`Any` 已在头）。

- [ ] **Step 2: 重写 `tool_nodes.py`**

- 顶部 import 收敛为：`Any`、`BadRequestError`、`RunContext`；删除 `UUID`/`TenantContext`/`AsyncSessionLocal`/`invoke_tool_with_context` 与 `_tenant_context_from_run` 函数（uuid 仍被 `_build_invoke_params` 用？——核对：`_build_invoke_params` 只用 `params`/`ctx.kb_ids`，无 UUID。`platform_tool` 中 `agent_id = UUID(ctx.agent_id)...` 随回调迁移而删）。
- 模块 docstring 更新调用链：`platform_tool` → `ctx.invoke_platform_tool`（L1 注入）→ `invoke_tool_with_context`。
- `platform_tool` 按「Architecture」verbatim 改造。
- 函数 `_build_invoke_params` 原样保留（含 docstring）。

- [ ] **Step 3: 定向测试（TDD 不强制，但须覆盖）**

新增/修改 `backend/tests/flow/test_tool_nodes.py`（若目录无此文件则新建）：
- 用例 A：`ctx.invoke_platform_tool` 为异步假回调（记录 slug/params/confirmed），`platform_tool` 返回 `{"output": {"ok": 1}, "tool_slug": "calculator"}`，断言透传（含 `confirmed=True` 与 `node_data confirmed=false` → `False`）。
- 用例 B：`invoke_platform_tool=None` 时 raise `BadRequestError`（或含「未装配」文案）。
- 用例 C：params 合并语义保留（`param_from_input`/`merge_input` 一例）。

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime/types.py app/flow_runtime/nodes/tool_nodes.py tests/flow/test_tool_nodes.py
uv run python -m pytest tests/flow/test_tool_nodes.py -q
rg -n "from app\.tenant\.tools|AsyncSessionLocal|TenantContext|uuid" app/flow_runtime/nodes/tool_nodes.py || echo "tool_nodes.py 净"
```
Expected：ruff 绿、新测试全过、rg 零命中。

> 注意：此时两根装配点尚未注入（Task 3），全量里真实画布工具执行会因 `invoke_platform_tool=None` 报「未装配」——**属计划内中间态**，本 Task 的 pytest 收口延至 Task 3 之后；本 Task 以定向测试 + ruff + rg 绿为准。

- [ ] **Step 4: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/tool_nodes.py
git commit -m "refactor(engine): platform_tool 节点改经 RunContext 回调执行工具

节点仅保留 slug/params 合并调度，执行迁入 L1 注入回调。"
```

---

### Task 2: L1 回调工厂 `flow_invoker.py`

**Files:**
- Create: `backend/app/tenant/tools/services/flow_invoker.py`

**Interfaces:**
- Consumes: `invoke_tool_with_context`（`tenant.tools.invoke`，本域）、`TenantContext`（`core.tenant`）、`AsyncSessionLocal`（`infra.db`）、`RunContext`（`flow_runtime.types`，L1→L3 注解）。
- Produces: `build_flow_tool_invoker() -> Callable`（Task 3 消费）。

- [ ] **Step 1: 实现（代码 verbatim）**

```python
"""画布平台工具执行回调工厂（L1）。

``build_flow_tool_invoker`` 构造 ``RunContext.invoke_platform_tool`` 回调：内部
把执行时 ctx 转 ``TenantContext``、开短会话并委托 ``invoke_tool_with_context``
（确认策略、Hook、调用日志）。原 ``flow_runtime/nodes/tool_nodes.py`` 内联执行
逻辑上移本模块，L3 节点只保留参数合并与调度。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from app.core.tenant import TenantContext
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.tenant.tools.invoke import invoke_tool_with_context


def build_flow_tool_invoker() -> Callable[..., Awaitable[dict[str, Any]]]:
    """构造画布工具执行回调：``(slug, params, ctx, *, confirmed) -> output``。"""

    async def _invoke(
        slug: str,
        params: dict[str, Any],
        ctx: RunContext,
        *,
        confirmed: bool,
    ) -> dict[str, Any]:
        uid = UUID(ctx.user_id) if ctx.user_id else UUID(int=0)
        tenant_ctx = TenantContext(
            user_id=uid,
            tenant_id=UUID(ctx.tenant_id),
            username="flow",
            is_superuser=ctx.is_superuser,
            permissions=ctx.permissions,
        )
        agent_id = UUID(ctx.agent_id) if ctx.agent_id else None
        async with AsyncSessionLocal() as db:
            return await invoke_tool_with_context(
                db,
                tenant_ctx,
                slug,
                params,
                confirmed=confirmed,
                actor_user_id=tenant_ctx.user_id,
                agent_id=agent_id,
                invoke_source="flow",
            )

    return _invoke
```

> 若 ruff 报 `_invoke` 返回类型仅注解问题可省略精确返回类型；保持与 `tenant/tools/invoke/context.py` 的 `invoke_tool_with_context` 返回类型一致（`dict`）。

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/tools/services/flow_invoker.py
uv run python -c "import app.tenant.tools.services.flow_invoker"
uv run python -c "from app.tenant.tools.services.flow_invoker import build_flow_tool_invoker; print(callable(build_flow_tool_invoker()))"
```
Expected：ruff 绿、import 成功、工厂返回可调用对象。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/tools/services/flow_invoker.py
git commit -m "refactor(engine): 画布工具执行回调工厂上移 L1 flow_invoker

供 RunContext.invoke_platform_tool 注入；含 tenant 上下文转换与短会话委托。"
```

---

### Task 3: 根装配点注入（chat_rag `flow_run_context` + flow debug-run）

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`

**Interfaces:**
- Consumes: Task 2 `build_flow_tool_invoker`。
- Produces: 两个根 `RunContext` 均带 `invoke_platform_tool`（Task 4 透传）。

- [ ] **Step 1: 两处装配**

在 `submit_generative_video=...` 关键字之后同批追加（两文件各一处；import `from app.tenant.tools.services.flow_invoker import build_flow_tool_invoker` 用函数级 import 放装配函数内，与文件既有风格一致）：

```python
                invoke_platform_tool=build_flow_tool_invoker(),
```

- `chat_rag.py`：`flow_run_context` 内 `return RunContext(...)`（现约 L88+）。
- `flows/services/flow.py`：debug-run 的 `ctx = RunContext(...)`（约 L255）。

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/agents/services/agent/chat_rag.py app/tenant/flows/services/flow.py
uv run python -m pytest tests/flow/test_tool_nodes.py tests/tenant/agents/test_agent_chat_rag_flow_context.py -q
```
Expected：ruff 绿、新/既有 flow 上下文测试过。**全量 pytest 收口点**：`uv run python -m pytest -q | tail -1` ≥ 456 passed（此前 tool 节点中间态「未装配」报错在装配后应消除——若仍有画布工具真实执行测试失败，核查该测试是否经 subflow/langgraph state 路径，属 Task 4 未透传的预期中间态，记入报告并在 Task 4 后再全量）。

> 若全量红因 Task 4 未做（langgraph state 丢失回调），允许本 Task 以「装配点定向 + 报告说明中间态」提交，Task 4 Step 2 为最终全量收口。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py
git commit -m "refactor(engine): 两根 RunContext 装配点注入平台工具执行回调"
```

---

### Task 4: LangGraph / subflow 透传

**Files:**
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`

**Interfaces:**
- Consumes: Task 1 `RunContext.invoke_platform_tool` 字段。
- Produces: state/子 context 全链路携带回调。

- [ ] **Step 1: 三处透传（与 `submit_generative_*` 逐点同构）**

- `compiler/run.py` `initial` dict：`submit_generative_video` 行后加 `"invoke_platform_tool": ctx.invoke_platform_tool,`。
- `compiler/build.py`：`_State` TypedDict 的 `submit_generative_video: Any` 后加 `invoke_platform_tool: Any`；`run_node` 闭包内 `RunContext(...)` 重建处 `submit_generative_video=state.get("submit_generative_video"),` 后加 `invoke_platform_tool=state.get("invoke_platform_tool"),`。
- `flow_runtime/subflow/resolve.py` `build_child_context`：`submit_generative_video=parent_ctx.submit_generative_video,  # 生视频异步提交回调透传到子流程` 后加 `invoke_platform_tool=parent_ctx.invoke_platform_tool,  # 平台工具执行回调透传到子流程`。

- [ ] **Step 2: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "invoke_platform_tool" app/integrations/langgraph/compiler/run.py app/integrations/langgraph/compiler/build.py app/flow_runtime/subflow/resolve.py
uv run ruff check app/integrations/langgraph/compiler app/flow_runtime/subflow/resolve.py
uv run python -m pytest -q | tail -1
```
Expected：三文件均有透传；ruff 绿；pytest ≥ 456 passed（**整支全量收口**）。

- [ ] **Step 3: Commit**

```bash
git add backend/app/integrations/langgraph/compiler/run.py backend/app/integrations/langgraph/compiler/build.py backend/app/flow_runtime/subflow/resolve.py
git commit -m "refactor(engine): langgraph state 与子流程透传平台工具执行回调"
```

---

### Task 5: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + rg 终审**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.tools|AsyncSessionLocal|TenantContext" app/flow_runtime/nodes/tool_nodes.py || echo "tool_nodes.py 对 tenant/infra 依赖清零"
uv run ruff check app/flow_runtime app/tenant/tools/services/flow_invoker.py
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中、ruff 绿、pytest ≥ 456。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：在 F2b 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-09，F2c-A）**：画布 `platform_tool` 节点执行回调注入——工具执行迁入 L1 `tenant/tools/services/flow_invoker.py::build_flow_tool_invoker`（构造 `TenantContext` + 短会话 + 委托 `invoke_tool_with_context`），`RunContext.invoke_platform_tool` 由两根装配点（`chat_rag.flow_run_context`/`flow.py` debug-run）注入并经 LangGraph state（`compiler/run.py`+`build.py`）与 subflow `build_child_context` 透传；`flow_runtime/nodes/tool_nodes.py` 只保留参数合并与调度，对 `tenant.tools.invoke`/`infra.db`/`TenantContext` 依赖清零（见 plan [`2026-09-09-engine-di-flow-tool-invoke`](../plans/2026-09-09-engine-di-flow-tool-invoke.md)）。`integrations/langchain/tool_agent/loop.py` 剩余 `tenant.tools.{confirmation,invoke}` 对话执行/确认面待 F2c-B。
```

§8 修订表 F2b 行之后追加：

```markdown
| 2026-09-09 | F2c-A：画布 `platform_tool` 执行回调 L1 `flow_invoker` 注入 `RunContext`，langgraph/subflow 透传；tool_nodes 对 `tenant.tools` 清零 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 F2c-A 画布工具执行回调注入"
```

---

## Self-Review

- **Spec coverage**：目标（`tool_nodes.py` 净 + 回调链路完整）由 Task 1（字段+节点）、Task 2（L1 工厂）、Task 3（根装配）、Task 4（state/subflow 透传）达成；Task 5 文档闭环。与 B-2e `submit_generative_*` 五改点逐一对应。
- **行为等价**：params 合并、confirmed、invoke_source="flow"、tenant ctx 构造（含 `UUID(int=0)` 兜底）、输出结构全部原样迁入 L1 回调；`_build_invoke_params` 留在节点未动。
- **依赖方向**：`flow_invoker.py`（L1）注解 import L3 `RunContext` 合法；节点残留仅 common/flow_runtime。
- **中间态**：Task 1-2 提交时画布真实工具执行因回调未注入而报「未装配」——按 B-2e 同款中间态策略记录，Task 3/4 逐步消除；Task 4 Step 2 为全量收口。
- **序列化**：langgraph state dict 存函数对象——B-2e `submit_*` 回调同款先例已证明可用。
- **Placeholder scan**：无 TBD；关键新代码 verbatim。
