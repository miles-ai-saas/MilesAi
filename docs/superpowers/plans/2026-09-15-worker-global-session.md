# Worker 内全局短会话清理 Implementation Plan

> **设计依据**：`docs/superpowers/specs/2026-09-14-rag-generation-db-connection-design.md` §10
> （机制、复现证据、站点清单、方法、生效前提均已在其中，本计划不重复设计，只做执行编排。）

**目标：** 把 Celery 任务内可达、但仍用全局 `AsyncSessionLocal()` 的短会话调用点换成
`short_db_session()`，使定时智能体任务（尤其走 LangGraph RAG 的）不再约半数失败。

**背景（一句话）：** Celery 任务用 `asyncio.run`，每次新 loop；全局 engine 池里是上一个 loop
创建的 asyncpg 连接，复用即抛 `RuntimeError: ... got Future attached to a different loop`。
控制端复现：连续 6 次 `asyncio.run`，全局会话在第 2/4/6 次失败，`get_worker_session()` 6/6 正常。

## Global Constraints

- 所有命令在 `backend/` 下执行，且必须用 `uv run --all-packages --group dev ...`
  —— 裸 `uv run` / `uv sync` 会卸载工作区其余成员包。
- 提交前门禁（五条）：`ruff format --check .`、`ruff check .`、`lint-imports`、
  `python -m miles_server.scripts.export_openapi --check`、`python -m pytest -q`。
  基线：**1044 passed, 2 warnings**（`Connection._cancel`，既有）。
- 测试输出保持干净：不得新增 warning。
- commit message 用**简体中文** + Conventional Commits，HEREDOC 传递。
- 分层约束：`miles_ai` ✗→ `miles_portal`；`miles_portal` ✗→ `miles_admin`；
  `miles_core` ✗→ `miles_ai`。`short_db_session` 来自 `miles_core.infra.db`，各层均可引用。
- 不新增依赖；不改 API 路由 / 响应字段 / OpenAPI 快照。
- **生效前提**（spec §10 已述，务必遵守）：`short_db_session()` 靠 `_worker_sessionmaker`
  这个 ContextVar 判断有无 worker engine，该变量由 `get_worker_session()` 在 `__aenter__`
  绑定、`__aexit__` **重置**。调用点必须落在 `get_worker_session()` 块**内**，否则会静默回退
  全局 = 等于没修。本计划全部站点已由终审确认在当前 Worker 调用子树内。

## 范围

**修（13 处 / 10 文件）**——Celery 任务内可达：

| 文件 | 行 | 站点 |
|------|----|------|
| `miles-ai/.../langgraph/graphs/rag_qa.py` | 67 | LangGraph `retrieve` 节点 |
| `miles-portal/.../models/services/usage.py` | 167 | `FlowUsageSink.record` |
| `miles-portal/.../tools/services/flow_invoker.py` | 40 | flow 工具调用 |
| `miles-portal/.../flows/services/run_context.py` | 25 | flow 模型解析 |
| `miles-portal/.../flows/services/subflow_loader.py` | 25 | 子流程图加载 |
| `miles-portal/.../prompts/services/template_loader.py` | 42 | 提示词模板加载 |
| `miles-portal/.../compliance/services/scan_words_loader.py` | 24 | 敏感词加载 |
| `miles-ai/.../flow_runtime/nodes/rag_nodes.py` | 48 | `KnowledgeSearch` 节点 |
| `miles-ai/.../flow_runtime/nodes/image_generate.py` | 55, 84 | 生图节点 |
| `miles-ai/.../flow_runtime/nodes/video_generate.py` | 56, 86 | 生视频节点 |

**不修**（判据：只在单 loop 进程内运行，无跨 loop 风险）：

- `miles-core/risk/enforce.py:42,87` —— 只被 Web 中间件与 Admin 服务调用
- `miles-portal/.../agents/ws/chat.py:114,160,185`、`ws/job_watch.py:72` —— WebSocket 端点
- `miles-server` 的 CLI 脚本（`backfill_media_assets.py:97`、`db_ops.py:58,69`）
- `miles-core/.../infra/db/async_session.py:54,107` —— 就是这两个函数自身

若实施中发现某个「不修」站点其实也落在 Worker 内，**停下报告**，不要顺手改（范围需重新裁决）。

---

### Task 1: 13 处调用点改用 `short_db_session()`

**Files:** 上表 10 个文件。

**Interfaces:**
- Consumes: `miles_core.infra.db.short_db_session`（已存在，`db/__init__.py` 已导出）
- Produces: 这 10 个模块不再引用全局 `AsyncSessionLocal`

- [ ] **Step 1: 逐个替换**

对每一处：把 `async with AsyncSessionLocal() as db:` 改为
`async with short_db_session() as db:`（变量名保持原样），import 从
`from miles_core.infra.db import AsyncSessionLocal` 改为
`from miles_core.infra.db import short_db_session`；若该文件还用到别的符号则并入括号。

`usage.py` 特殊：它已同时导入两者（`FlowUsageSink` 与 `ChatUsageSink`），
本 Task 后 `AsyncSessionLocal` 不再被该文件使用 ⇒ 从 import 行删掉它。

- [ ] **Step 2: 全仓确认这 10 个文件已无全局短会话**

Run:
```bash
rg -n "AsyncSessionLocal\(\)" packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/rag_qa.py \
  packages/miles-portal/src/miles_portal/tenant/models/services/usage.py \
  packages/miles-portal/src/miles_portal/tenant/tools/services/flow_invoker.py \
  packages/miles-portal/src/miles_portal/tenant/flows/services/run_context.py \
  packages/miles-portal/src/miles_portal/tenant/flows/services/subflow_loader.py \
  packages/miles-portal/src/miles_portal/tenant/prompts/services/template_loader.py \
  packages/miles-portal/src/miles_portal/tenant/compliance/services/scan_words_loader.py \
  packages/miles-ai/src/miles_ai/flow_runtime/nodes/rag_nodes.py \
  packages/miles-ai/src/miles_ai/flow_runtime/nodes/image_generate.py \
  packages/miles-ai/src/miles_ai/flow_runtime/nodes/video_generate.py
```
Expected: 无输出。

- [ ] **Step 3: 跑测试**

Run: `uv run --all-packages --group dev python -m pytest tests/ -q`
Expected: 全绿（行为不变——API 路径回退全局，Worker 路径改用同 loop engine）。

- [ ] **Step 4: 门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add <上表 10 个文件>
git commit -F - <<'EOF'
fix(worker): 流程与 RAG 节点短会话改走 short_db_session

这些调用点都在 Celery 任务内可达，而 asyncio.run 每次新建 loop，全局
engine 池里属于上一个 loop 的连接复用即抛「got Future attached to a
different loop」——定时智能体任务据此约半数失败（走 LangGraph RAG 时必现
检索节点）。

统一改用 short_db_session：Worker 内绑当前 loop 的 engine，API/CLI 单
loop 进程回退全局，行为不变。
EOF
```

---

### Task 2: 同形护栏 + 结构不变量

**为什么：** spec §10.5 指出被 defer 的站点「仍无护栏」。上一轮的实际教训是：护栏弱会让
连接处置不变量悄悄腐化（I1 就是这样漏过 8 个任务的评审）。本 Task 为每个站点补
「全局会话被换成调用即炸替身」的用例。

**Files:** 各站点对应的既有测试文件；必要时新增。

- [ ] **Step 1: 逐站点补护栏**

对每个站点，在既有测试文件中（无则新建）加一条用例，形态统一：

```python
class _Boom:
    """全局会话替身：一旦被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")
```

- 用 `monkeypatch.setattr(mod, "short_db_session", <记录用替身>)` 让站点走替身；
- 用 `monkeypatch.setattr(mod, "AsyncSessionLocal", _Boom(), raising=False)` 钉住回退；
- 断言业务结果不变（即站点确实完成原职责，而不是只断言「没炸」）。

已有对应文件（直接在其中加用例）：
`tests/rag/test_rag_qa_nodes_share_generate.py`（或在 `tests/flow/test_langgraph_rag.py`）、
`tests/tenant/models/test_flow_usage_sink.py`、
`tests/tenant/flows/test_subflow_loader.py`、
`tests/tenant/prompts/test_template_loader.py`、
`tests/tenant/compliance/test_scan_words_loader.py`、
`tests/flow/test_generative_nodes.py`（生图/生视频）、
`tests/flow/test_prompt_template_node.py`（`rag_nodes`）。
`flow_invoker` 与 `run_context` 若无可挂靠文件，新建
`tests/tenant/tools/test_flow_invoker_session.py` /
`tests/tenant/flows/test_run_context_session.py`。

- [ ] **Step 2: 加一条结构不变量（防复发）**

新增 `tests/infra/test_no_global_session_in_worker_paths.py`：断言上表 10 个模块的命名空间
里**没有** `AsyncSessionLocal`，且**有** `short_db_session`。

```python
EXPECTED_SHORT_SESSION_MODULES = [...10 个模块路径...]

@pytest.mark.parametrize("path", EXPECTED_SHORT_SESSION_MODULES)
def test_worker_reachable_modules_use_short_session(path: str) -> None:
    mod = importlib.import_module(path)
    assert not hasattr(mod, "AsyncSessionLocal"), f"{path} 不得直接引用全局会话（见 spec §10）"
    assert hasattr(mod, "short_db_session"), f"{path} 应改用 short_db_session"
```

- [ ] **Step 3: 验证护栏真的会红（逐个回退实验）**

至少抽 3 处（`rag_qa.py` 检索节点、`usage.py` 的 `FlowUsageSink`、`image_generate.py`）
临时改回 `AsyncSessionLocal`，确认对应用例 FAIL，再逐字还原。
Expected: 三处均 FAIL 且失败信息指向「不得回退全局」；还原后全绿。

- [ ] **Step 4: 门禁 + Commit**

```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check && \
uv run --all-packages --group dev python -m pytest -q
```
```bash
git add <测试文件>
git commit -F - <<'EOF'
test(worker): 为短会话站点补齐护栏与结构不变量

被 deferred 的站点此前没有护栏，而弱护栏正是上一轮让连接处置不变量腐化
的原因。为每个站点补「全局会话换成调用即炸替身」的用例，并加一条结构断言
钉住「这 10 个模块不得再引用 AsyncSessionLocal」，防止改动回流。
EOF
```

---

### Task 3: 终检

- [ ] **Step 1: Worker 形态端到端验证**

真库探针（放 `/tmp`，不提交）：连续 6 次 `asyncio.run`，每轮复刻 `agent_schedule` 结构
（`get_worker_session()` 块**内**依次调用新改的站点，至少覆盖 `rag_qa` 检索节点与
`FlowUsageSink.record`）。Expected: **6/6 ok**；作为对照，把其中一处改回全局应出现约半数 FAIL。

- [ ] **Step 2: 五条门禁**

同 Task 1 Step 4。Expected: 全绿，测试数 = 基线 + 新增护栏数。

- [ ] **Step 3: 更新 spec §10 状态**

把 §10 从「遗留（本分支未修）」改为已修：标题、§10.4、§10.5 同步；保留机制与复现证据
（对后续仍有价值），并在 §9 修订记录追加一条（日期 2026-09-15）。

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-rag-generation-db-connection-design.md
git commit -F - <<'EOF'
docs(spec): §10 遗留站点已修复，同步状态

原 §10 记录的 10 文件 13 处 Worker 同险站点已改用 short_db_session 并补
护栏，机制与复现证据保留供后续参考。
EOF
```

---

## 自检记录

**Spec 覆盖核对**

| spec §10 内容 | 对应 Task |
|---|---|
| 机制与复现证据 | 无需改动（保留） |
| §10.3 已修 3 处 | 上一分支已完成 |
| §10.4 未修 10 文件 13 处 | Task 1 |
| §10.4 生效前提（须在 worker 块内） | 计划 Global Constraints；Task 3 Step 1 端到端验证 |
| §10.5 护栏覆盖现状 | Task 2 |
| §10 标题/状态 | Task 3 Step 3 |

**占位符扫描**：无 TBD / TODO；每个改动步骤给出完整代码或精确替换指令。
Task 2 的文件清单为「优先挂靠既有文件、无则新建」的二选一，属有意留白（取决于实施者
落点），已在计划中写明两种路径。

**开放风险**：本计划假设 spec §10.4 的站点清单完备。若 Task 1 Step 2 的扫查或 Task 2 的
结构不变量测试暴露出清单外的 Worker 可达站点，**停下报告**并重新裁决范围。
