# G2-1 实施计划：flow 子流程加载/校验面收敛——L3 仓储契约 + RunContext 回调注入

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/subflow/{resolve,validate}.py`（L3）对 `tenant.flows.repositories.flow.FlowRepository` 的运行期 import——运行期子图加载（`subflow_nodes`/`loop_nodes`）改经 L3 中性回调 `RunContext.load_subflow_graph` + L1 loader 注入；编译期校验（`validate_subflow_references`，由 L1 `FlowService` 调用）改接收 L3 中性仓储契约 `FlowRepoLike`（结构由 `FlowRepository` 满足，L1 传 `self.repo`）。这是 flow 画布节点面（G2）收敛第三个子计划。

**完成标准：**
- `flow_runtime/subflow/` 内 `from app.tenant.*` 清零（`resolve.py`/`validate.py`/`contracts.py`）。
- `RunContext.load_subflow_graph: Callable[[dict, str], Awaitable[dict]] | None`（L1 注入；None 且 SubFlow/LoopNode 节点执行时报错）。
- `resolve_subflow_graph(repo, ...)` / `validate_subflow_references(repo, ...)` 以 `FlowRepoLike` 契约标注，不再 import `AsyncSession`/`FlowRepository`。
- 行为等价：published/pinned 策略、未发布/无版本/pinned 缺失/不存在/自引用/环/深度超限错误码与文案、子图执行与输出结构全保留。
- 全量测试 ≥ 481，回归无行为变化。

## 背景事实（已审计）

- `subflow/resolve.py` 反依赖仅 1 处：L19 `from app.tenant.flows.repositories.flow import FlowRepository`；`resolve_subflow_graph(db, node_data, tenant_id)` 内 `repo = FlowRepository(db)` 后按 policy（published/pinned）取 `get_by_id`/`get_version`，返回 `graph_json`。其余函数（`iter_subflow_nodes`/`_parse_sub_flow_id`/`build_child_context`/`pick_subflow_output`/`summarize_child_steps`）无 tenant 依赖。
- `subflow/validate.py` 反依赖 1 处：L21 同 import；`validate_subflow_references(db, graph, *, tenant_id, current_flow_id)` 内自建 `FlowRepository(db)`，内部 helper（`_load_flow_graph_for_analysis`/`_direct_subflow_ids`/`_max_chain_depth`）均已形参 `repo: FlowRepository`（改类型即可）。
- 运行期调用方（L3 节点，各自 `AsyncSessionLocal()` 短会话 + `UUID(ctx.tenant_id)`）：
  - `nodes/subflow_nodes.py::sub_flow` L40-45；
  - `nodes/loop_nodes.py::loop_node` L57-63。
- 编译期调用方（L1）：`tenant/flows/services/flow.py::_compile_report_for_flow` L312 `validate_subflow_references(self.db, ...)`——`FlowService.__init__` 已持有 `self.repo = FlowRepository(db)`（L68），可直接传 `self.repo`。
- `FlowRepoLike` 仅需两方法：`get_by_id(entity_id, *, include_deleted=False) -> T | None`（`app/core/repository.py`）、`get_version(flow_id, version) -> FlowVersion | None`（`tenant/flows/repositories/flow.py`）。校验逻辑另读 `flow.id/tenant_id/status/current_version`（duck-typing）。
- 既有测试：`tests/flow/test_subflow.py` 仅覆盖 `build_child_context`/`iter_subflow_nodes`/编译器校验（无 DB），**未**直接测 `resolve_subflow_graph`/`validate_subflow_references`/节点；需新增（fake repo / fake callback）。
- RunContext 注入模式同 G2-2/G2-3（None 默认 + 双根装配点 + langgraph state + subflow 透传）。`build_child_context` 已透传 `resolve_prompt_template`/`load_scan_words` 等。
- 先例：F2c-B `tool_agent/tool_contract.py`（L3 中性契约 Protocol）；G2-2/G2-3 loader 下沉 L1。

**Architecture:**

- **L3 中性契约**（新建 `flow_runtime/subflow/contracts.py`）：
  ```python
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
  ```
- **`validate.py` 注入**：签名 `validate_subflow_references(repo: FlowRepoLike, graph, *, tenant_id, current_flow_id)`；删 `FlowRepository`/`AsyncSession` import（`AsyncSession` 仅签名用），加 `FlowRepoLike` import；内部 helper 类型标注 `FlowRepository` → `FlowRepoLike`；函数体不建 repo。
- **`resolve.py` 注入**：签名 `resolve_subflow_graph(repo: FlowRepoLike, node_data, tenant_id)`；删 `FlowRepository`/`AsyncSession` import，加 `FlowRepoLike`；函数体不建 repo。
- **RunContext 回调**（`flow_runtime/types.py`，随 `load_scan_words` 之后）：
  ```python
  # 画布 SubFlow/LoopNode 子流程图加载回调（L1 注入；签名 (node_data, tenant_id) -> graph_json；
  # None 表示未装配，节点报错）。新建画布 RunContext 根装配点须随 resolve_generative_*
  # 一并注入（见 chat_rag/flow debug-run）。
  load_subflow_graph: Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]] | None = None
  ```
- **L1 loader**（新建 `tenant/flows/services/subflow_loader.py`）：
  - `def build_subflow_graph_loader() -> Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]`：无参工厂，闭包 `async def _loader(node_data, tenant_id)`：`UUID(tenant_id)` → `async with AsyncSessionLocal() as db:` → `return await resolve_subflow_graph(FlowRepository(db), node_data, tid)`。
- **节点改造**（`subflow_nodes.py`/`loop_nodes.py`）：删 `AsyncSessionLocal`（及仅用于 tenant_id 转换的 `UUID`）import；`resolve_subflow_graph` 调用段替换为：
  ```python
      if ctx.load_subflow_graph is None:
          raise BadRequestError("运行上下文未提供子流程图加载回调")
      graph_json = await ctx.load_subflow_graph(node_data, ctx.tenant_id)
  ```
  其余逻辑（深度校验、child ctx、run_subflow、输出结构）逐字保留。
- **透传**：`build_child_context` 已透传同族回调，追加 `load_subflow_graph=parent_ctx.load_subflow_graph`。

## Global Constraints

- 分层：改后 `flow_runtime/subflow/` 对 `tenant.*` import 清零；`contracts.py` 为 L3 中性（禁止 import tenant）；`subflow_loader.py` 为 L1（import L3 `resolve_subflow_graph` + 同域 `FlowRepository` + `infra.db`，合法）；L1 `flow.py` 传 `self.repo` 结构满足契约。
- 行为等价：错误码（`missing_sub_flow_id`/`subflow_self`/`subflow_not_found`/`subflow_pinned_missing`/`subflow_not_published`/`subflow_cycle`/`subflow_max_depth`）与文案、pinned/published 分支、深度计算与环检测全保留；节点输出结构不变。
- 中文 docstring；改动 ≤ 450 行。
- 每任务定向 + 全量回归（基线 **481 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: L3 仓储契约 `contracts.py` + `validate.py` 注入 + L1 调用点

**Files:**
- Create: `backend/app/flow_runtime/subflow/contracts.py`
- Modify: `backend/app/flow_runtime/subflow/validate.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Create: `backend/tests/flow/test_subflow_validate.py`

**Interfaces:**
- Produces: `FlowRepoLike`（Task 2 消费）；`validate_subflow_references(repo, ...)`（L1 调用点已切换）。

- [ ] **Step 1: `contracts.py`**

按 Architecture 建 `FlowRepoLike`（两方法 verbatim）。

- [ ] **Step 2: `validate.py` 注入**

- 签名 `validate_subflow_references(db: AsyncSession, graph, *, tenant_id, current_flow_id)` → `validate_subflow_references(repo: FlowRepoLike, graph, *, tenant_id, current_flow_id)`；删函数体首行 `repo = FlowRepository(db)`。
- 删 `from sqlalchemy.ext.asyncio import AsyncSession`、`from app.tenant.flows.repositories.flow import FlowRepository`；加 `from app.flow_runtime.subflow.contracts import FlowRepoLike`。
- 内部 helper（`_load_flow_graph_for_analysis`/`_direct_subflow_ids`/`_max_chain_depth`）`repo: FlowRepository` → `repo: FlowRepoLike`（三处）。
- 其余逻辑**逐字保留**（错误码/文案/分支）。
- 模块 docstring 补一句：仓储以 `FlowRepoLike` 契约注入（L1 `FlowService` 传 `FlowRepository`）。

- [ ] **Step 3: L1 调用点**

`flow.py::_compile_report_for_flow`：`validate_subflow_references(self.db, ...)` → `validate_subflow_references(self.repo, ...)`。

- [ ] **Step 4: 定向测试（fake repo）**

新建 `tests/flow/test_subflow_validate.py`（用 `types.SimpleNamespace` 造 Flow、async 假 repo）：
- 用例 A（缺 sub_flow_id / 自引用 / 非法 UUID）：无需 repo 调用（假 repo 方法设为会 raise），断言对应错误码。
- 用例 B（子流程不存在）：`repo.get_by_id` 返回 None → `subflow_not_found`。
- 用例 C（未发布）：flow `status != PUBLISHED`（用 `app.models.flow.FlowStatus.DRAFT`）→ `subflow_not_published`。
- 用例 D（pinned 版本缺失）：`version_policy="pinned"`、`pinned_version=9`，`repo.get_version` 返回 None → `subflow_pinned_missing`。
- 用例 E（通过）：已发布 + `current_version=1` + `get_version` 返回 `SimpleNamespace(graph_json={"nodes": [], "edges": []})` → 无对应错误（且 depth 未超限）。
- 用例 F（深度超限，可选）：构造链式引用使 `_max_chain_depth > MAX_SUBFLOW_DEPTH` → `subflow_max_depth`。
Flow 假对象字段：`id`/`tenant_id`/`status`/`current_version`（无 `deleted_at` 即 `is_marked_deleted` 为 False）。

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime/subflow app/tenant/flows/services/flow.py tests/flow/test_subflow_validate.py
uv run python -m pytest tests/flow/test_subflow_validate.py tests/flow/test_subflow.py -q
```
Expected：ruff 绿；用例全过。

- [ ] **Step 5: Commit**

```bash
git add backend/app/flow_runtime/subflow/contracts.py backend/app/flow_runtime/subflow/validate.py backend/app/tenant/flows/services/flow.py backend/tests/flow/test_subflow_validate.py
git commit -m "refactor(engine): subflow 校验改走 L3 仓储契约注入

validate_subflow_references 接收 FlowRepoLike，L1 FlowService 传 self.repo，
消除 subflow/validate 对 tenant 仓储的运行时依赖。"
```

---

### Task 2: 运行期子图加载回调 + `resolve.py` 注入 + 节点切换

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Create: `backend/app/tenant/flows/services/subflow_loader.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify: `backend/app/flow_runtime/nodes/subflow_nodes.py`
- Modify: `backend/app/flow_runtime/nodes/loop_nodes.py`
- Modify: `backend/tests/flow/test_subflow.py`
- Create: `backend/tests/flow/test_subflow_runtime.py`
- Create: `backend/tests/tenant/flows/test_subflow_loader.py`

**Interfaces:**
- Consumes: Task 1 `FlowRepoLike`。
- Produces: `RunContext.load_subflow_graph`、`build_subflow_graph_loader()`（Task 3 消费）。

- [ ] **Step 1: RunContext 字段**

`flow_runtime/types.py`：`load_scan_words` 之后追加 Architecture 段 `load_subflow_graph` 字段。

- [ ] **Step 2: `resolve.py` 注入**

- 签名 `resolve_subflow_graph(db: AsyncSession, node_data, tenant_id)` → `resolve_subflow_graph(repo: FlowRepoLike, node_data, tenant_id)`；删函数体 `repo = FlowRepository(db)`。
- 删 `from sqlalchemy.ext.asyncio import AsyncSession`、`from app.tenant.flows.repositories.flow import FlowRepository`；加 `from app.flow_runtime.subflow.contracts import FlowRepoLike`。
- policy 分支与错误文案**逐字保留**。
- 模块 docstring 补一句：子图加载经 `FlowRepoLike` 契约（L1 `build_subflow_graph_loader` 注入短会话仓储）。

- [ ] **Step 3: L1 loader**

`tenant/flows/services/subflow_loader.py`（结构见 Architecture；docstring 说明装配点为 chat_rag flow_run_context / flow debug-run）。

- [ ] **Step 4: 节点切换**

`subflow_nodes.py` / `loop_nodes.py`：
- 删 `from app.infra.db import AsyncSessionLocal`；`from uuid import UUID` 若仅用于旧 tenant_id 转换则删（核对）。
- `resolve_subflow_graph` 调用段（含 `async with AsyncSessionLocal() as db:`）替换为 Architecture 段（None → `BadRequestError("运行上下文未提供子流程图加载回调")`）。
- 其余逐字保留。

- [ ] **Step 5: 透传**

`resolve.py::build_child_context` 的 `RunContext(...)` 实参加 `load_subflow_graph=parent_ctx.load_subflow_graph,  # 子流程图加载回调透传到子流程`。

- [ ] **Step 6: 测试**

1. `tests/flow/test_subflow.py`：`test_build_child_context_forwards_resolve_model_and_usage_sink` 加 `load_subflow_graph=fake_subflow_loader,`（async 假函数）与 `assert child.load_subflow_graph is fake_subflow_loader`。
2. 新建 `tests/flow/test_subflow_runtime.py`：
   - `resolve_subflow_graph` fake repo：published → 返回 graph_json；pinned 缺失 → `BadRequestError`；未发布 → `BadRequestError`（断言文案关键字）。
   - `sub_flow` 节点：`ctx.load_subflow_graph=fake`（返回 `{"nodes": [], "edges": []}`）+ `ctx.run_subflow=fake`（返回 `SimpleNamespace(output="x", steps=[])`）→ 断言输出 `output == "x"`、`child_flow_id`；`load_subflow_graph=None` → `BadRequestError("运行上下文未提供子流程图加载回调")`。
   - `loop_node` 节点：`load_subflow_graph=None` → 同报错；有回调 + `max_iterations=1` → 迭代 1 次。
3. 新建 `tests/tenant/flows/test_subflow_loader.py`：monkeypatch `subflow_loader.AsyncSessionLocal`（假 async 上下文）+ `subflow_loader.FlowRepository`（记录 db）+ `subflow_loader.resolve_subflow_graph`（记录 (repo, node_data, tid)）→ 断言委托与 tenant UUID 解析；工厂可调用。

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/subflow/ || echo "subflow 包对 tenant import 清零"
uv run ruff check app/flow_runtime/subflow app/flow_runtime/nodes app/tenant/flows/services/subflow_loader.py tests/flow/test_subflow_runtime.py tests/tenant/flows/test_subflow_loader.py
uv run python -m pytest tests/flow/test_subflow.py tests/flow/test_subflow_runtime.py tests/tenant/flows/test_subflow_loader.py -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；定向全过；全量 ≥ 481 passed。

- [ ] **Step 7: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/subflow/resolve.py backend/app/flow_runtime/nodes/subflow_nodes.py backend/app/flow_runtime/nodes/loop_nodes.py backend/app/tenant/flows/services/subflow_loader.py backend/tests/flow/test_subflow.py backend/tests/flow/test_subflow_runtime.py backend/tests/tenant/flows/test_subflow_loader.py
git commit -m "refactor(engine): SubFlow/LoopNode 子图加载改走 RunContext 回调

resolve_subflow_graph 接收 FlowRepoLike，L1 subflow_loader 注入短会话仓储，
subflow 包对 tenant 依赖清零。"
```

---

### Task 3: 装配注入 + langgraph 透传 + 文档闭环

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py`
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 双根装配点注入**

- `chat_rag.py::flow_run_context`：函数级 import `from app.tenant.flows.services.subflow_loader import build_subflow_graph_loader`（与 `build_scan_words_loader` 并列）；`RunContext(...)` 在 `load_scan_words=...,` 之后加 `load_subflow_graph=build_subflow_graph_loader(),`。
- `flows/services/flow.py::run`（debug-run）：同上。

- [ ] **Step 2: langgraph state 透传**

- `compiler/run.py`：initial state 加 `"load_subflow_graph": ctx.load_subflow_graph,`。
- `compiler/build.py`：`_State` 加 `load_subflow_graph: Any`（附 L1 注入注释）；`run_node` 的 `RunContext(...)` 重建加 `load_subflow_graph=state.get("load_subflow_graph"),`。

- [ ] **Step 3: 装配断言**

`tests/tenant/agents/test_agent_chat_rag_flow_context.py`：按既有 `load_scan_words` 断言模式追加 `ctx.load_subflow_graph is not None` + `callable(...)`。

- [ ] **Step 4: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/subflow/ || echo "subflow 包对 tenant import 清零"
uv run ruff check app/flow_runtime app/tenant/flows app/tenant/agents/services/agent/chat_rag.py app/integrations/langgraph/compiler
uv run python -m pytest tests/flow tests/tenant/flows tests/tenant/agents -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；定向全过；全量 ≥ 481 passed。

- [ ] **Step 5: 文档 + 两次 commit**

`docs/architecture/layering.md`：G2-3 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-09，G2-1）**：画布 SubFlow/LoopNode 子图加载与编译期校验收敛——L3 中性仓储契约 `flow_runtime/subflow/contracts.py::FlowRepoLike`；运行期加载经 `RunContext.load_subflow_graph` 回调（L1 `tenant/flows/services/subflow_loader.py::build_subflow_graph_loader` 注入短会话 `FlowRepository`），编译期 `validate_subflow_references(repo, ...)` 由 L1 `FlowService` 传 `self.repo`；`flow_runtime/subflow/` 对 `tenant.*` import 清零（见 plan [`2026-09-09-engine-di-flow-subflow-loader`](../plans/2026-09-09-engine-di-flow-subflow-loader.md)）。
```

§8 修订表 G2-3 行之后追加：

```markdown
| 2026-09-09 | G2-1：flow 子流程加载/校验收敛——FlowRepoLike 契约 + RunContext.load_subflow_graph 回调，subflow 包对 tenant 清零 |
```

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py backend/app/integrations/langgraph/compiler/run.py backend/app/integrations/langgraph/compiler/build.py backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py
git commit -m "refactor(engine): 装配注入与透传 load_subflow_graph 回调"

git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G2-1 子流程加载/校验收敛"
```

---

## Self-Review

- **Spec coverage**：目标（subflow 包对 tenant import 清零）由 Task 1（校验面 repo 契约注入）+ Task 2（运行期回调 + resolve 注入 + 节点切换）+ Task 3（装配/state/文档）达成。
- **行为等价**：`validate_subflow_references` 全部分支/错误码/文案逐字保留（仅 repo 来源由自建改注入）；`resolve_subflow_graph` policy 与错误文案逐字保留；节点输出结构与深度校验不变。`FlowRepository` 结构满足 `FlowRepoLike`，L1 传参零语义变化。
- **依赖方向**：`contracts.py`/`resolve.py`/`validate.py` 只在 L3 内 + `models.flow`/`infra`/`core.soft_delete`（合法）；`subflow_loader.py` L1 引 L3 与同域仓储（向下/同层合法）；L1 调用点传 `self.repo`。
- **中间态**：Task 1 签名改 + L1 调用点同 commit（无断裂）；Task 2 签名改 + 两节点切换 + 透传同 commit（无断裂）；Task 3 装配闭环。langgraph state 透传在 Task 3（同 G2-2/G2-3 先例）。
- **测试罩**：新增 validate fake-repo 6 用例 + resolve/node 运行期用例 + loader 单测 + `build_child_context` 透传断言 + 装配断言；全量 ≥ 481。
- **Placeholder scan**：无 TBD；关键新代码（contracts/loader/节点片段）verbatim 或逐字锚点。
