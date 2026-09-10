# G2-3 实施计划：flow ComplianceCheck 节点收敛——纯算法下沉 models + 词表加载回调注入

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/compliance_nodes.py`（L3）对 `tenant.compliance.services.{pipeline,word_resolve}` 的运行期 import——纯算法（`CompliancePipeline`/`ScanMatch`/`ScanResult`/`SensitiveAction`）下沉中立域 `app/models/compliance/`，租户词表加载（原 `get_sync_db` + `load_tenant_scan_words`）改经 L3 中性回调 `RunContext.load_scan_words` + L1 loader 注入。这是 flow 画布节点面（G2）收敛第二个子计划。

**完成标准：**
- `compliance_nodes.py` 内 `from app.tenant.*` 清零；同步 `get_sync_db` 阻塞调用移除（改 async 回调）。
- `RunContext.load_scan_words: Callable[[str], Awaitable[Any]] | None`（L1 注入；None 且节点执行时报错）。
- 行为等价：词表为空 → `passed=True/未配置敏感词库`；无文本 → `passed=True/无输入文本`；命中/`mode=block` 的 `hits/hit_count/passed/blocked/text` 结构全保留；`CompliancePipeline` 匹配语义（大小写不敏感子串、BLOCK 优先）不变。
- 全量测试 ≥ 469，回归无行为变化。

## 背景事实（已审计）

- `compliance_nodes.py` 反依赖（3 处）：
  1. L15 `from app.tenant.compliance.services.pipeline import CompliancePipeline`（纯算法，仅依赖 `SensitiveAction` 枚举）。
  2. L16 `from app.tenant.compliance.services.word_resolve import load_tenant_scan_words`（DB 查询：租户已绑定启用词库 → `[(word, SensitiveAction)]`）。
  3. L13 `from app.infra.db import get_sync_db`（L3 合法，但收敛后不再需要）；L45 `words = load_tenant_scan_words(db, UUID(ctx.tenant_id))` 在 `with get_sync_db()` 内**同步阻塞**。
- `CompliancePipeline`（`tenant/compliance/services/pipeline.py`，46 行）纯内存算法：`ScanMatch(word, action)` / `ScanResult(matches)`（`has_block`/`has_warn`/`worst_action`）/ `CompliancePipeline(words).scan(text)`，唯一外部依赖 `app.tenant.compliance.models.SensitiveAction`。
- `SensitiveAction(str, enum.Enum)` 定义在 `tenant/compliance/models.py`（L17-19），被 ORM（`SAEnum`、`InterceptLog.action`）/schemas/meta/`intercept.py`/`word_resolve.py` 引用——**同名同类**下沉后经 shim re-export 可保全部路径不变。
- `merge_scan_words` 亦纯函数但仅 L1 `load_tenant_scan_words` 消费（无 L3 依赖），**本次不迁**（避免无收益的 shim 面）。
- `intercept.py`（L1，`ComplianceInterceptMixin`）import `CompliancePipeline` 与 `load_tenant_scan_words`——shim 后路径不变，无需改动。
- 既有测试：**无** compliance 节点/pipeline 直接测试（`rg` 零命中），需新建；回归罩为流程/langgraph 全量。
- RunContext 注入模式同 G2-2：字段 None 默认 + 双根装配点（`chat_rag.flow_run_context` / `flows/services/flow.py::run`）+ langgraph state（`compiler/run.py`/`build.py`）+ subflow `build_child_context` 透传。
- 先例：F2b 将工具参数纯函数下沉 `app/models/tool/parameters.py`、原路径转 re-export shim；B-2d 将枚举下沉 `app/models/agent/constants.py` + `tenant.agents.constants` re-export。

**Architecture:**

- **中立域** `app/models/compliance/`：
  - `__init__.py`：docstring（说明该包为合规纯逻辑中立域，L1 shim 见 `tenant.compliance.{models,services.pipeline}`）。
  - `constants.py`：`SensitiveAction` 枚举 verbatim（自 `tenant/compliance/models.py` 迁入，含 `"""..."""` 说明）。
  - `pipeline.py`：`ScanMatch` / `ScanResult` / `CompliancePipeline` verbatim（自 `tenant/compliance/services/pipeline.py` 迁入），`SensitiveAction` 自 `app.models.compliance.constants` import。
- **tenant shim**：
  - `tenant/compliance/models.py`：删 `import enum` 与 `SensitiveAction` 类定义，改 `from app.models.compliance.constants import SensitiveAction`（本地 `_sensitive_action_enum`/`InterceptLog.action` 仍使用，属真实引用非纯 re-export，无需 noqa）。
  - `tenant/compliance/services/pipeline.py`：改 re-export shim `from app.models.compliance.pipeline import CompliancePipeline, ScanMatch, ScanResult  # noqa: F401`（L1 `intercept.py` 路径稳定）。
- **RunContext 回调**（`flow_runtime/types.py`，随 `resolve_prompt_template` 之后）：
  ```python
  # 画布 ComplianceCheck 节点敏感词表加载回调（L1 注入；签名 (tenant_id) -> [(word, action)]；
  # None 表示未装配，节点报错）。新建画布 RunContext 根装配点须随 resolve_generative_*
  # 一并注入（见 chat_rag/flow debug-run）。
  load_scan_words: Callable[[str], Awaitable[Any]] | None = None
  ```
- **L1 loader**（新建 `tenant/compliance/services/scan_words_loader.py`）：
  - `def build_scan_words_loader() -> Callable[[str], Awaitable[Any]]`：无参工厂，闭包 `async def _loader(tenant_id: str)`：`UUID(tenant_id)` → `async with AsyncSessionLocal() as db:` → `return await load_tenant_scan_words(db, tenant_id_uuid)`。
- **节点改造**（`compliance_nodes.py`）：
  - 删 L13 `get_sync_db`、L15/L16 tenant import、`UUID` import（仅用于旧 `UUID(ctx.tenant_id)`）；加 `from app.models.compliance.pipeline import CompliancePipeline`。
  - 词表加载段改为：`if ctx.load_scan_words is None: raise BadRequestError("运行上下文未提供敏感词加载回调")` → `words = await ctx.load_scan_words(ctx.tenant_id)`；其余（空词表返回、`CompliancePipeline(words).scan(text)`、返回结构）全保留。
  - 模块 docstring 中「通过 AttachmentService/词库读取」类描述同步为「词表经 RunContext.load_scan_words（L1 注入）加载」。

## Global Constraints

- 分层：改后 `compliance_nodes.py` 对 `tenant.*` import 清零（允许 `models.compliance.pipeline`/`common`/`flow_runtime`）；`scan_words_loader.py` 为 L1（import `tenant.compliance.services.word_resolve` + `infra.db` 合法）；`app/models/compliance/*` 为中立域（禁止 import `tenant.*`/`integrations.*`）；新增 import 均向下，禁止反向。
- 行为等价：`ScanResult` 属性、匹配语义、节点返回字段（`passed`/`hits`/`hit_count`/`mode`/`blocked`/`text`/`reason`）与文案全保留；仅 DB 访问由 sync → async（语义增强，不改变结果）。
- 中文 docstring；改动 ≤ 350 行。
- 每任务定向 + 全量回归（基线 **469 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: 中立域 `app/models/compliance/` + tenant shim + pipeline 单测

**Files:**
- Create: `backend/app/models/compliance/__init__.py`
- Create: `backend/app/models/compliance/constants.py`
- Create: `backend/app/models/compliance/pipeline.py`
- Modify: `backend/app/tenant/compliance/models.py`
- Modify: `backend/app/tenant/compliance/services/pipeline.py`
- Create: `backend/tests/models/test_compliance_pipeline.py`

**Interfaces:**
- Produces: `SensitiveAction`（中立）、`CompliancePipeline`/`ScanMatch`/`ScanResult`（中立）；tenant 两处 shim 保路径（Task 3 消费中立 pipeline）。

- [ ] **Step 1: 中立域三文件**

- `__init__.py`：docstring（合规模块纯逻辑中立域；L1 re-export shim 见 `tenant/compliance/models.py` 与 `tenant/compliance/services/pipeline.py`）。
- `constants.py`：迁入 `SensitiveAction` 定义（verbatim；docstring 说明「敏感词处置动作，ORM/schemas/L3 共用」）。
- `pipeline.py`：迁入 `ScanMatch`/`ScanResult`/`CompliancePipeline`（verbatim），`from app.models.compliance.constants import SensitiveAction`。

- [ ] **Step 2: tenant shim**

- `tenant/compliance/models.py`：删 `import enum`；删 `SensitiveAction` 类定义；改 `from app.models.compliance.constants import SensitiveAction`（置于既有 `from app.models.base import ...` 附近，按项目 import 排序）。
- `tenant/compliance/services/pipeline.py`：整文件替换为 re-export shim：
  ```python
  """敏感词流水线（re-export shim）。

  实现已下沉中立域 ``app.models.compliance.pipeline``；保留本路径供 L1 既有引用
  （``compliance/services/compliance/intercept.py`` 等）。
  """

  from app.models.compliance.pipeline import (  # noqa: F401
      CompliancePipeline,
      ScanMatch,
      ScanResult,
  )
  ```

- [ ] **Step 3: 中立 pipeline 单测（TDD）**

`tests/models/test_compliance_pipeline.py`（新建 `tests/models/`）：
- 命中 + BLOCK 优先：`CompliancePipeline([("foo", WARN), ("bar", BLOCK)])` → scan("FOO bar") → 2 命中，`has_block` True，`worst_action` BLOCK。
- 大小写不敏感 / 空白裁剪：词表含 `" Foo "` 能命中 "foo"。
- 空文本 / 空词表 → `matches == ()`、`has_block/has_warn/worst_action` 语义。
- `from app.tenant.compliance.services.pipeline import CompliancePipeline` 与中立路径为**同一对象**（shim 等价性断言）。

Run（backend/ 下）：
```bash
uv run ruff check app/models/compliance app/tenant/compliance/models.py app/tenant/compliance/services/pipeline.py tests/models/test_compliance_pipeline.py
uv run python -m pytest tests/models/test_compliance_pipeline.py -q
```
Expected：ruff 绿；用例全过。

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/compliance backend/app/tenant/compliance/models.py backend/app/tenant/compliance/services/pipeline.py backend/tests/models/test_compliance_pipeline.py
git commit -m "refactor(engine): 合规扫描纯算法下沉中立域 models/compliance

CompliancePipeline/SensitiveAction 迁入 app.models.compliance，
tenant 路径转 re-export shim，供 L3 画布节点直接引用。"
```

---

### Task 2: `RunContext.load_scan_words` + L1 loader + 定向单测

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Create: `backend/app/tenant/compliance/services/scan_words_loader.py`
- Create: `backend/tests/tenant/compliance/test_scan_words_loader.py`

**Interfaces:**
- Consumes: `load_tenant_scan_words`（`tenant.compliance.services.word_resolve`）、`AsyncSessionLocal`（`infra.db`）。
- Produces: `RunContext.load_scan_words`、`build_scan_words_loader()`（Task 3/4 消费）。

- [ ] **Step 1: RunContext 字段**

`flow_runtime/types.py`：`resolve_prompt_template` 字段后追加 Architecture 段 `load_scan_words` 字段（注释块风格一致）。

- [ ] **Step 2: L1 loader**

`tenant/compliance/services/scan_words_loader.py`：
```python
"""画布 ComplianceCheck 节点敏感词表加载器（L1 装配）。

``build_scan_words_loader`` 构造 ``RunContext.load_scan_words`` 回调：按 tenant_id
短会话加载租户已绑定启用词库的启用词条（``load_tenant_scan_words``），供
flow_runtime ComplianceCheck 节点使用；装配点为 chat_rag.flow_run_context 与
flows flow debug-run。
"""
```
- `def build_scan_words_loader() -> Callable[[str], Awaitable[Any]]`：闭包 `async def _loader(tenant_id: str)`：`UUID(tenant_id)` → `async with AsyncSessionLocal() as db:` → `return await load_tenant_scan_words(db, tid)`。

- [ ] **Step 3: 定向单测**

`tests/tenant/compliance/test_scan_words_loader.py`（新建目录）：
- 用例 A（委托 + 短会话）：monkeypatch `scan_words_loader.AsyncSessionLocal` 为假 async 上下文管理器、monkeypatch `scan_words_loader.load_tenant_scan_words` 为 async 假实现（记录 (db, tenant_uuid) 并返回 `[("foo", SensitiveAction.WARN)]`）→ `_loader(str(tenant_uuid))` 返回该列表，且 tenant_uuid 解析正确。
- 用例 B（工厂可调用）：`build_scan_words_loader()` 返回 callable（async）。

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime/types.py app/tenant/compliance/services/scan_words_loader.py tests/tenant/compliance/test_scan_words_loader.py
uv run python -m pytest tests/tenant/compliance/test_scan_words_loader.py -q
uv run python -c "from app.flow_runtime.types import RunContext; assert RunContext(tenant_id='1').load_scan_words is None; print('ok')"
```
Expected：ruff 绿；用例全过；默认 None。

- [ ] **Step 4: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/tenant/compliance/services/scan_words_loader.py backend/tests/tenant/compliance/test_scan_words_loader.py
git commit -m "refactor(engine): ComplianceCheck 词表加载器下沉 L1 并加 RunContext 回调

load_scan_words 经 build_scan_words_loader 注入，消除画布节点 tenant 反依赖。"
```

---

### Task 3: `compliance_nodes.py` 契约化 + 节点测试（TDD）

**Files:**
- Modify: `backend/app/flow_runtime/nodes/compliance_nodes.py`
- Create: `backend/tests/flow/test_compliance_node.py`

**Interfaces:**
- Consumes: Task 1 中立 `CompliancePipeline`、Task 2 `RunContext.load_scan_words`。
- Produces: `compliance_nodes.py` 对 `tenant.*` import 清零。

- [ ] **Step 1: 节点改造**

- import：删 `from uuid import UUID`、`from app.infra.db import get_sync_db`、两行 tenant import；加 `from app.models.compliance.pipeline import CompliancePipeline`（保留 `BadRequestError`/`RunContext`/`Any`）。
- `compliance_check` 词表段：
  ```python
  if ctx.load_scan_words is None:
      raise BadRequestError("运行上下文未提供敏感词加载回调")
  words = await ctx.load_scan_words(ctx.tenant_id)
  ```
  （替换原 `with get_sync_db() as db: words = load_tenant_scan_words(db, UUID(ctx.tenant_id))`）
- 其余逻辑（`input_key` 取值、空文本早返回、空词表返回、pipeline.scan、hits/passed/mode/blocked/text 返回）**逐字保留**。
- 模块 docstring：「读取租户已绑定词库」一句改述为「词表经 ``RunContext.load_scan_words``（L1 注入）加载；``CompliancePipeline`` 来自中立域 ``app.models.compliance.pipeline``」。

- [ ] **Step 2: 节点测试（TDD）**

`tests/flow/test_compliance_node.py`（`pytest.mark.asyncio`）：
- 用例 A（命中 + warn）：`ctx = RunContext(tenant_id=..., load_scan_words=<async 返回 [("敏感词", WARN)]>)` → node_data `{"mode": "warn"}`、inputs `{"input": "含敏感词文本"}` → `passed=False`、`hit_count=1`、`blocked=False`、`hits[0]["word"]`、`text` 截断字段存在。
- 用例 B（mode=block + BLOCK 命中）：词表含 BLOCK → `blocked=True`。
- 用例 C（空词表）：回调返回 `[]` → `passed=True`、`reason="未配置敏感词库"`。
- 用例 D（无输入文本）：inputs `{}` → `passed=True`、`reason="无输入文本"`、`text=""`（且**不触发**回调——回调可设为会 raise 的假实现以证明未调用）。
- 用例 E（None 回调）：`ctx` 无回调 + 有文本 → `pytest.raises(BadRequestError)`（match「敏感词加载回调」）。
- 用例 F（`input_key` 自定义）：node_data `{"input_key": "foo"}`、inputs `{"foo": "..."}` 生效。

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/compliance_nodes.py || echo "compliance_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime/nodes/compliance_nodes.py tests/flow/test_compliance_node.py
uv run python -m pytest tests/flow/test_compliance_node.py -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；节点测试全过；pytest ≥ 469 passed。

- [ ] **Step 3: Commit**

```bash
git add backend/app/flow_runtime/nodes/compliance_nodes.py backend/tests/flow/test_compliance_node.py
git commit -m "refactor(engine): ComplianceCheck 节点改走中立 pipeline 与词表回调

词表经 ctx.load_scan_words 注入、算法引中立域，tenant import 与同步阻塞清零。"
```

---

### Task 4: 装配注入 + 透传 + 文档闭环

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify: `backend/tests/flow/test_subflow.py`
- Modify: `backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py`
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 双根装配点注入**

- `chat_rag.py::flow_run_context`：函数级 import `from app.tenant.compliance.services.scan_words_loader import build_scan_words_loader`（与 `build_prompt_template_loader` 并列）；`RunContext(...)` 实参在 `resolve_prompt_template=` 之后加 `load_scan_words=build_scan_words_loader(),`。
- `flows/services/flow.py::run`：同上。

- [ ] **Step 2: langgraph state + subflow 透传**

- `compiler/run.py`：initial state 加 `"load_scan_words": ctx.load_scan_words,`。
- `compiler/build.py`：`_State` 加 `load_scan_words: Any`；`run_node` 的 `RunContext(...)` 重建加 `load_scan_words=state.get("load_scan_words"),`。
- `subflow/resolve.py::build_child_context`：加 `load_scan_words=parent_ctx.load_scan_words,  # 敏感词表加载回调透传到子流程`。

- [ ] **Step 3: 测试断言扩展**

- `tests/flow/test_subflow.py`：parent 构造加 `load_scan_words=fake_words_loader,`（async 假函数），断言区加 `assert child.load_scan_words is fake_words_loader`。
- `tests/tenant/agents/test_agent_chat_rag_flow_context.py`：追加 `ctx.load_scan_words is not None` + `callable(...)` 断言（与该文件既有 resolve_prompt_template 断言并列）。

- [ ] **Step 4: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/compliance_nodes.py || echo "compliance_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime app/tenant/agents/services/agent/chat_rag.py app/tenant/flows/services/flow.py app/integrations/langgraph/compiler app/models/compliance app/tenant/compliance
uv run python -m pytest tests/flow/test_subflow.py tests/tenant/agents/test_agent_chat_rag_flow_context.py tests/flow/test_compliance_node.py -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；定向全过；pytest ≥ 469 passed。

- [ ] **Step 5: 文档 + Commit**

`docs/architecture/layering.md`：在 G2-2 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-09，G2-3）**：画布 ComplianceCheck 节点收敛——纯算法 `CompliancePipeline`/`ScanMatch`/`ScanResult`/`SensitiveAction` 下沉中立域 `app.models.compliance`（`tenant.compliance.{models,services.pipeline}` 转 re-export shim），租户词表加载经 `RunContext.load_scan_words` 回调（L1 `tenant/compliance/services/scan_words_loader.py::build_scan_words_loader`）注入；`flow_runtime/nodes/compliance_nodes.py` 对 `tenant.*` import 与同步 `get_sync_db` 阻塞清零（见 plan [`2026-09-09-engine-di-flow-compliance-node`](../plans/2026-09-09-engine-di-flow-compliance-node.md)）。
```

§8 修订表 G2-2 行之后追加：

```markdown
| 2026-09-09 | G2-3：flow ComplianceCheck 节点收敛——合规纯算法下沉 models/compliance + 词表加载 RunContext 回调，compliance_nodes 对 tenant 清零 |
```

代码与文档分两次 commit：
```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py backend/app/integrations/langgraph/compiler/run.py backend/app/integrations/langgraph/compiler/build.py backend/app/flow_runtime/subflow/resolve.py backend/tests/flow/test_subflow.py backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py
git commit -m "refactor(engine): 装配注入与透传 load_scan_words 回调"

git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G2-3 ComplianceCheck 节点收敛"
```

---

## Self-Review

- **Spec coverage**：目标（`compliance_nodes` 对 tenant import 清零 + 词表回调注入 + 纯算法下沉）由 Task 1（中立域 + shim）+ Task 2（回调字段 + L1 loader）+ Task 3（节点改造 + 测试）+ Task 4（装配/透传/文档）达成。
- **行为等价**：节点返回字段与文案全保留；`CompliancePipeline` 与 `SensitiveAction` 为**同名同类对象**（shim 导入同一对象，ORM `SAEnum`/schemas/meta 行为不变，Task 1 含等价性断言）；唯一差异是 DB 访问 sync → async（不改变词表结果）。
- **依赖方向**：中立域不 import tenant（Task 1 审）；节点仅引中立层；loader 在 L1 引同域 + infra；装配点 L1 同层。
- **中间态**：Task 1 纯迁移 + shim（L1 调用方零改动，全量可跑）；Task 2 纯新增；Task 3 节点切换 + 测试同 commit；Task 4 装配闭环。
- **测试罩**：新增中立 pipeline 单测 + loader 单测 + 节点 6 用例 + subflow/装配断言；全量 ≥ 469。
- **Placeholder scan**：无 TBD；关键改造给 verbatim/逐字锚点。
