# G2-2 实施计划：flow PromptTemplate 节点模板库 live 引用收敛——RunContext 回调注入

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/rag_nodes.py`（L3）对 `tenant.prompts.models.PromptTemplate` 的运行期 import——模板库 live 引用加载经 L3 中性回调（`RunContext.resolve_prompt_template`）+ L1 loader（`tenant/prompts/services/template_loader.py::build_prompt_template_loader`）注入。这是 flow 画布节点面（G2）收敛的第一个子计划。

**完成标准：**
- `rag_nodes.py` 内 `from app.tenant.*` 清零；`_load_prompt_template_content` 移除（迁 L1）。
- `RunContext.resolve_prompt_template: Callable[[str, str], Awaitable[str | None]] | None`（L1 注入；None 且节点引用 `prompt_template_id` 时报错）。
- 行为等价：live 引用优先、内联 `template` 兜底、默认 `_DEFAULT_PROMPT_TEMPLATE`、占位符替换、system_prompt 前缀全保留；live 引用校验（tenant/is_active/not_deleted）在 L1 loader 内原样保留。
- 全量测试 ≥ 464，回归无行为变化。

## 背景事实（已审计）

- `rag_nodes.py` 顶部 L25 `from app.tenant.prompts.models import PromptTemplate`；模块 docstring 描述 KnowledgeSearch 与 PromptTemplate 两类节点。
- `_load_prompt_template_content(prompt_template_id: str, tenant_id: str) -> str | None`：`AsyncSessionLocal()` 短会话 → `db.get(PromptTemplate, tid)` → tenant_uuid + `is_active` + `not is_marked_deleted` 校验 → 返回 content；UUID 解析失败返回 None。
- `_resolve_node_template(node_data, ctx)`：`prompt_template_id` 存在则 live 加载（成功即返回），否则内联 `template`，再否则 `_DEFAULT_PROMPT_TEMPLATE`。
- `prompt_template` 节点再拼 `ctx.system_prompt` 前缀。
- RunContext 现有 L1 注入回调模式（均 None 默认、装配点注入）：`resolve_model`/`kb_retrieval`/`resolve_generative_*`/`submit_generative_*`/`invoke_platform_tool`，经 langgraph state（`compiler/run.py` initial dict + `compiler/build.py` `_State`/`run_node`）与 subflow `build_child_context`（`subflow/resolve.py`）透传。两根根装配点：`chat_rag.py::flow_run_context`、`flows/services/flow.py::run`（debug-run）。
- 测试罩：`tests/flow/test_prompt_template_node.py` 现有 4 用例直接 monkeypatch `rag_nodes._load_prompt_template_content`（live 引用 / fallback / inline / system_prompt 前缀）——收敛后改为经 `ctx.resolve_prompt_template` 注入断言。
- `_load_prompt_template_content` 原实现校验用 `tpl.tenant_id == tenant_uuid`、`tpl.is_active`、`not is_marked_deleted(tpl)`，`is_marked_deleted` 自 `app.core.soft_delete`；L1 loader 原样搬移。

**Architecture:**

- **RunContext 回调**（`flow_runtime/types.py` 增字段，随 `invoke_platform_tool` 注释块之后）：
  ```python
  # 画布 PromptTemplate 节点模板库 live 引用解析回调（L1 注入；
  # 签名 (prompt_template_id, tenant_id) -> content|None；None 表示未装配，
  # 节点引用 prompt_template_id 时报错）。新建画布 RunContext 根装配点
  # 须随 resolve_generative_* 一并注入（见 chat_rag/flow debug-run）。
  resolve_prompt_template: Callable[[str, str], Awaitable[str | None]] | None = None
  ```
- **L1 loader**（新建 `tenant/prompts/services/template_loader.py`）：
  - `build_prompt_template_loader() -> Callable[[str, str], Awaitable[str | None]]`：无参工厂，返回闭包——复制原 `_load_prompt_template_content` 的短会话 + 校验逻辑（UUID 解析失败 → None；查无/非租户/非启用/已删 → None）。模块 docstring 说明供 `RunContext.resolve_prompt_template` 装配。
  - 内部可拆 `async def _load_prompt_template(db, tid, tenant_uuid) -> str | None` 便于单测（db 注入），工厂闭包负责开 `AsyncSessionLocal` 短会话与 UUID 解析。
- **rag_nodes 改造**：删 `PromptTemplate` import 与 `_load_prompt_template_content`；`_resolve_node_template` 改调 `ctx.resolve_prompt_template`，`ctx.resolve_prompt_template is None` 且存在 `prompt_template_id` → `BadRequestError("运行上下文未提供 prompt 模板解析回调")`；模块 docstring 中「模板库 live 引用经 L1 回调」说明。`knowledge_search` 保留既有短会话检索（G2 后续另项处理）。

## Global Constraints

- 分层：改后 `rag_nodes.py` 对 `tenant.*` import 清零（L3 允许 `app.infra.db`/`app.rag.generate`/`app.common`/`flow_runtime` 内部）；`template_loader.py` 为 L1（import `tenant.prompts.models` + `infra.db` + `core.soft_delete` 均合法）；新增 import 均向下，禁止反向。
- 行为等价：live 引用 → 内联 → 默认模板三级解析、占位符、system_prompt 前缀、live 引用校验（tenant/is_active/not_deleted）全保留；None 回调仅在节点引用模板库时报错（inline/默认模板路径不受影响）。
- 中文 docstring；改动 ≤ 300 行。
- 每任务定向 + 全量回归（基线 **464 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: RunContext 回调字段 `resolve_prompt_template`

**Files:**
- Modify: `backend/app/flow_runtime/types.py`

**Interfaces:**
- Produces: `RunContext.resolve_prompt_template` 字段（Task 2/3/4 消费）。

- [ ] **Step 1: 实现**

`RunContext` dataclass：在 `invoke_platform_tool` 字段定义之后追加 Architecture 段字段（含注释块），保持现有注释风格。

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime/types.py
uv run python -c "from app.flow_runtime.types import RunContext; c=RunContext(tenant_id='1'); assert c.resolve_prompt_template is None; print('ok')"
```
Expected：ruff 绿；默认 None。

- [ ] **Step 3: Commit**

```bash
git add backend/app/flow_runtime/types.py
git commit -m "refactor(engine): RunContext 增 prompt 模板解析回调字段

供 PromptTemplate 节点 live 引用经 L1 loader 注入，消除 tenant 反依赖。"
```

---

### Task 2: L1 loader `template_loader.py` + 定向单测

**Files:**
- Create: `backend/app/tenant/prompts/services/template_loader.py`
- Create: `backend/tests/tenant/prompts/test_template_loader.py`

**Interfaces:**
- Consumes: `PromptTemplate`（`tenant.prompts.models`）、`AsyncSessionLocal`（`infra.db`）、`is_marked_deleted`（`core.soft_delete`）。
- Produces: `build_prompt_template_loader()`（Task 3/4 消费）。

- [ ] **Step 1: 实现**

`tenant/prompts/services/template_loader.py`（结构见 Architecture，代码要点）：
```python
"""画布 PromptTemplate 节点模板库 live 引用加载器（L1 装配）。

``build_prompt_template_loader`` 构造 ``RunContext.resolve_prompt_template`` 回调：
按 ``prompt_template_id`` + ``tenant_id`` 加载启用中模板的 content（live 引用非快照），
供 flow_runtime PromptTemplate 节点使用。原实现迁自 flow_runtime/nodes/rag_nodes.py。
"""
```
- `async def _load_prompt_template(db, template_id: UUID, tenant_id: UUID) -> str | None`：`db.get(PromptTemplate, template_id)` + 校验（同原实现）→ content | None。
- `def build_prompt_template_loader() -> Callable[[str, str], Awaitable[str | None]]`：返回闭包 `async def _loader(prompt_template_id, tenant_id)`：UUID 解析（失败 → None）→ `async with AsyncSessionLocal() as db:` 委托 `_load_prompt_template`。
- 顶部 docstring 补：装配点为 chat_rag flow_run_context / flow debug-run。

- [ ] **Step 2: 定向单测（TDD）**

`tests/tenant/prompts/test_template_loader.py`：
- 用例 A（加载成功）：monkeypatch `template_loader.AsyncSessionLocal` 为假 async 上下文管理器（enter 返回假 db），假 db.get 返回启用的模板对象 → `_loader(template_id, tenant_id)` 返回 content，且校验字段被读（tenant_id/is_active）。
- 用例 B（UUID 非法 → None）：`_loader("not-a-uuid", "1")` 返回 None，不触 db。
- 用例 C（校验失败 → None）：db.get 返回非租户模板 / is_active=False / 已删 → None（可参数化或单选代表）。
- 用例 D（工厂返回可调用 + 委托解析）：`build_prompt_template_loader()` 返回 async callable，调用时经 `_load_prompt_template` 语义路径。

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/prompts/services/template_loader.py tests/tenant/prompts/test_template_loader.py
uv run python -m pytest tests/tenant/prompts/test_template_loader.py -q
```
Expected：ruff 绿；用例全过。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/prompts/services/template_loader.py backend/tests/tenant/prompts/test_template_loader.py
git commit -m "refactor(engine): prompt 模板 live 引用加载器下沉 L1

build_prompt_template_loader 供 RunContext.resolve_prompt_template 装配。"
```

---

### Task 3: `rag_nodes.py` 契约化 + 测试迁移

**Files:**
- Modify: `backend/app/flow_runtime/nodes/rag_nodes.py`
- Modify: `backend/tests/flow/test_prompt_template_node.py`

**Interfaces:**
- Consumes: Task 1 `RunContext.resolve_prompt_template`、Task 2 loader（装配在 Task 4，本 Task 仅节点侧）。
- Produces: `rag_nodes.py` 对 `tenant.*` import 清零。

- [ ] **Step 1: `rag_nodes.py` 改造**

- 删 L25 `from app.tenant.prompts.models import PromptTemplate` 与 `_load_prompt_template_content` 整函数。
- `_resolve_node_template(node_data, ctx)`：`prompt_template_id` 分支改：
  ```python
  prompt_template_id = node_data.get("prompt_template_id")
  if prompt_template_id:
      if ctx.resolve_prompt_template is None:
          raise BadRequestError("运行上下文未提供 prompt 模板解析回调")
      loaded = await ctx.resolve_prompt_template(str(prompt_template_id), ctx.tenant_id)
      if loaded:
          return loaded
  ```
- 模块 docstring：PromptTemplate 节点 live 引用一句改指「经 RunContext.resolve_prompt_template（L1 注入）加载」。
- 核对 `AsyncSessionLocal` 仍被 `knowledge_search` 使用 → 保留 import。
- 核对 `is_marked_deleted`：原仅 `_load_prompt_template_content` 使用？若删函数后无他用则一并删 import（`knowledge_search` 用否？查——如无则删）。

- [ ] **Step 2: 测试迁移**

`tests/flow/test_prompt_template_node.py`：
- `test_prompt_template_live_reference`：去掉 monkeypatch `_load_prompt_template_content`，改为构造 `ctx = RunContext(tenant_id=tenant_id, resolve_prompt_template=<async 假实现>)`，断言假实现收到 `(template_id, tenant_id)` 且 content 生效。
- `test_prompt_template_live_reference_fallback_to_inline`：同改 ctx 注入返回 None 的假实现，断言回退内联。
- 新增用例：`resolve_prompt_template=None` 且 `prompt_template_id` 存在 → `pytest.raises(BadRequestError)`（inline 模板不触发）。
- inline / placeholders / system_prompt 三用例不变（不涉 live 引用）。

- [ ] **Step 3: 验证 + 回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/rag_nodes.py || echo "rag_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime/nodes/rag_nodes.py tests/flow/test_prompt_template_node.py
uv run python -m pytest tests/flow/test_prompt_template_node.py -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；节点测试全过；pytest ≥ 464 passed。

- [ ] **Step 4: Commit**

```bash
git add backend/app/flow_runtime/nodes/rag_nodes.py backend/tests/flow/test_prompt_template_node.py
git commit -m "refactor(engine): rag_nodes 模板 live 引用改走 ctx 回调

PromptTemplate 节点经 resolve_prompt_template 注入加载，tenant import 清零。"
```

---

### Task 4: 装配注入 + 透传 + 文档闭环

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify（如有现成装配断言测试）: `backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py`
- Modify: `backend/tests/flow/test_subflow.py`
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 两根根装配点注入**

- `chat_rag.py::flow_run_context`：函数级 import `build_prompt_template_loader`（与 `build_flow_tool_invoker` import 并列），`RunContext(...)` 实参加 `resolve_prompt_template=build_prompt_template_loader(),`（`invoke_platform_tool=` 之后）。
- `flows/services/flow.py::run`（debug-run）：同上（与 `invoke_platform_tool=build_flow_tool_invoker(),` 并列加）。

- [ ] **Step 2: langgraph state + subflow 透传**

- `compiler/run.py`：initial state dict 加 `"resolve_prompt_template": ctx.resolve_prompt_template,`。
- `compiler/build.py`：`_State` TypedDict 加 `resolve_prompt_template: Any`；`run_node` 的 `RunContext(...)` 重建加 `resolve_prompt_template=state.get("resolve_prompt_template"),`。
- `subflow/resolve.py::build_child_context`：`RunContext(...)` 实参加 `resolve_prompt_template=parent_ctx.resolve_prompt_template,  # prompt 模板解析回调透传到子流程`。

- [ ] **Step 3: 测试扩展**

- `tests/flow/test_subflow.py`：既有 build_child_context 透传断言测试（现断言 resolve_model/usage_sink/submit_generative_*/invoke_platform_tool 等）追加 `resolve_prompt_template` 透传断言。
- 装配断言：若存在 `test_agent_chat_rag_flow_context.py`（B-2e hardening 建的装配等价性单测），追加断言 `flow_run_context` 产物 ctx.resolve_prompt_template 非 None 且为 async callable；若无此文件则跳过（由全量回归覆盖装配正确性——flow 场景带 PromptTemplate 节点的集成路径）。
- `tests/flow/test_langgraph_compiler.py`（若含 state/RunContext 重建断言）按需追加同断言。

- [ ] **Step 4: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/rag_nodes.py || echo "rag_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime app/tenant/agents/services/agent/chat_rag.py app/tenant/flows/services/flow.py app/integrations/langgraph/compiler app/tenant/prompts/services/template_loader.py
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；pytest ≥ 464 passed（含 prompt 节点、subflow、langgraph、agents 全罩）。

- [ ] **Step 5: 文档 + Commit**

`docs/architecture/layering.md`：找 F2c-B 收敛记录，其后追加：

```markdown
> **收敛记录（2026-09-09，G2-2）**：画布 PromptTemplate 节点模板库 live 引用收敛——`RunContext.resolve_prompt_template` 回调（L1 注入），loader `tenant/prompts/services/template_loader.py::build_prompt_template_loader` 承载原租户校验/短会话逻辑；`flow_runtime/nodes/rag_nodes.py` 删 `tenant.prompts.models` import（见 plan [`2026-09-09-engine-di-flow-prompt-loader`](../superpowers/plans/2026-09-09-engine-di-flow-prompt-loader.md)）。flow 画布节点面（G2）收敛起点。
```

§8 修订表 F2c-B 行之后追加：

```markdown
| 2026-09-09 | G2-2：flow PromptTemplate 节点模板 live 引用收敛——RunContext.resolve_prompt_template 回调 + L1 template_loader，rag_nodes 对 tenant 清零（G2 画布节点面起点） |
```

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G2-2 prompt 模板 live 引用收敛"
```

---

## Self-Review

- **Spec coverage**：目标（rag_nodes 对 tenant import 清零 + 回调注入）由 Task 1（字段）+ Task 2（L1 loader）+ Task 3（节点改造 + 测试迁移）+ Task 4（装配/透传/文档）达成。
- **行为等价**：live 引用 → inline → 默认三级解析不变；tenant/is_active/not_deleted 校验在 L1 loader 原样保留；None 回调仅当节点引用模板库时抛 BadRequestError（inline/默认路径不受影响，语义安全）。
- **依赖方向**：回调字段/类型在 L3（rag_nodes 同层）；loader 在 L1（import tenant.prompts.models + infra.db 向下合法）；装配点 L1 import loader 同层。rag_nodes 剩余 import 全部 L3/`infra.db`/`rag.generate`/`common`。
- **中间态**：Task 1/2 纯新增不破坏既有；Task 3 节点切换 + 测试同步迁移（同 commit）；Task 4 装配注入完成行为闭环。
- **测试罩**：prompt 节点 4 用例迁移 + None 报错新用例 + loader 4 用例 + subflow 透传断言 + 装配断言（若有装配测试文件）。
- **Placeholder scan**：无 TBD；loader 与节点改造均给 verbatim 结构；UUID 解析失败语义与原实现一致（返回 None）。
