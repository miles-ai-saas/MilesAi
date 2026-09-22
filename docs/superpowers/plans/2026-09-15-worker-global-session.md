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

**修（12 处 / 10 文件）**——Celery 任务内可达：

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

### Task 1: 12 处调用点改用 `short_db_session()`

**Files:**
- Modify: 上表 10 个源文件
- Modify: 6 个既有测试文件（见 Step 1b）

**Interfaces:**
- Consumes: `miles_core.infra.db.short_db_session`（已存在，`db/__init__.py` 已导出）
- Produces: 这 10 个模块不再引用全局 `AsyncSessionLocal`；既有测试改为打桩 `short_db_session`

- [ ] **Step 1: 逐个替换**

对每一处：把 `async with AsyncSessionLocal() as db:` 改为
`async with short_db_session() as db:`（变量名保持原样），import 从
`from miles_core.infra.db import AsyncSessionLocal` 改为
`from miles_core.infra.db import short_db_session`；若该文件还用到别的符号则并入括号。

`usage.py` 特殊：它已同时导入两者（`FlowUsageSink` 与 `ChatUsageSink`），
本 Task 后 `AsyncSessionLocal` 不再被该文件使用 ⇒ 从 import 行删掉它。

- [ ] **Step 1b: 迁移既有测试的打桩目标（控制端 errata，2026-09-15）**

原计划只列了 10 个源文件，漏了这一点：6 个既有测试文件用**无 `raising=False`** 的
`monkeypatch.setattr(mod, "AsyncSessionLocal", ...)` 注入假会话。源模块移除该符号后，
它们会整齐抛 `AttributeError`（实测 16 failed / 1028 passed）。这些打桩的意图是
「替换会话工厂」，故应指向模块现在使用的那一个。

逐处把被替换的属性名由 `AsyncSessionLocal` 改为 `short_db_session`（`lambda:` /
假上下文管理器工厂的形状不变——`short_db_session` 是 `@asynccontextmanager`，
与 `AsyncSessionLocal()` 一样返回异步上下文管理器）：

| 测试文件 | 打桩处数 | 被替换的模块 |
|---|---|---|
| `tests/flow/test_generative_nodes.py` | 6 | `image_node` / `video_node` |
| `tests/tenant/prompts/test_template_loader.py` | 4 | `template_loader` |
| `tests/tenant/models/test_flow_usage_sink.py` | 3 | `usage_mod` |
| `tests/tenant/flows/test_subflow_loader.py` | 1 | `loader_mod` |
| `tests/tenant/compliance/test_scan_words_loader.py` | 1 | `loader_mod` |
| `tests/tenant/agents/test_rag_usage_accumulation.py` | 1 | `rag_qa` |

连同各文件里描述该替身的 docstring/注释一并更新（如「假 AsyncSessionLocal」→
「假 short_db_session」），避免注释与代码脱节。

> 注意：**不要**动那些带 `raising=False` 的护栏（`test_short_db_session.py`、
> `test_flow_media_reader.py`、`test_chat_usage_sink_session.py`、
> `test_chat_usage_accumulation.py`、`test_chat_rag_connection_release.py`）——
> 它们有意打桩「可能不存在的全局名」，正是为了在回退时炸出来。

- [ ] **Step 2: 全仓确认这 10 个文件已无全局短会话**

Run:
```bash
rg -n "AsyncSessionLocal\(\)" packages/miles-integrations/src/miles_ai/rag/graph/rag_qa.py \
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
git add <上表 10 个源文件> <Step 1b 的 6 个测试文件>
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
| §10.4 未修站点（计数口径见 spec §10.4 表） | Task 1 |
| §10.4 生效前提（须在 worker 块内） | 计划 Global Constraints；Task 3 Step 1 端到端验证；Task 4 Step 2 组合护栏 |
| §10.5 护栏覆盖现状 | Task 2 |
| §10 标题/状态 | Task 3 Step 3 |

**占位符扫描**：无 TBD / TODO；每个改动步骤给出完整代码或精确替换指令。
Task 2 的文件清单为「优先挂靠既有文件、无则新建」的二选一，属有意留白（取决于实施者
落点），已在计划中写明两种路径。

**开放风险**：本计划假设 spec §10.4 的站点清单完备。若 Task 1 Step 2 的扫查或 Task 2 的
结构不变量测试暴露出清单外的 Worker 可达站点，**停下报告**并重新裁决范围。

---

### Task 4: 终审修复（guard 强度 + 生产缺陷 + 记述准确性）

**来源：** 全分支终审（`.superpowers/sdd/final-review.md`）。判 Ready，无 Critical，但 3 条 Important
中两条直指本分支自己的护栏强度，另有一条真实生产缺陷。控制端已逐条独立核实。

- [ ] **Step 1（Important-2）交叉核对扩到「谁可以碰全局会话」**

现状：`_discover_short_session_call_sites` 只看得见 `short_db_session(`，所以**新增**一个直接用
`async with AsyncSessionLocal()` 的模块 → 交叉核对与不变量测试全绿（实测 17 passed）。而
docstring 宣称「新增站点会立刻以清单缺项失败」——该保证对最危险的回归形态不成立。

改为：用 `ast` 枚举 `packages/*/src/**/*.py` 中**引用** `AsyncSessionLocal` 的模块（import 或
调用均为 `ast.Name`，故注释/字符串天然不算），断言该集合**恰好等于**一份显式 allowlist
（`EXCLUDED_INFRA_MODULES` + `EXCLUDED_SINGLE_LOOP_MODULES`）。这样「谁可以碰全局会话」从
隐式惯例变成必须显式登记的决策，新模块要么走 `short_db_session`，要么被有意识地列入
allowlist（并在那里接受 loop 安全性审查）。

- [ ] **Step 2（Important-1）补一条覆盖「组合」的已提交测试**

现状：13 条站点护栏只断言「本模块引用了 `short_db_session`」，没有任何已提交测试断言
「站点在 worker 块**内**运行时确实拿到 worker 工厂、在块**外**回退全局」。实测：注入
「`get_worker_session()` 不再绑定 ContextVar」的回归后 **1081/1082 仍绿**（唯一失败的是既有
helper 测试，不是任何一条新护栏）——即计划里标为「务必遵守」的前提只靠一个未提交的 `/tmp`
探针兜着。

新增 hermetic 测试：以 `get_worker_session()` 的块形态驱动一个**真实站点**（取
`progress.update_generative_job_progress`），断言块内该站点拿到 worker 工厂；块外拿到全局。
断言要落在「用了哪个工厂」上，而不是「没抛异常」。

- [ ] **Step 3（Minor，真实缺陷）worker engine 走 `build_engine`**

`packages/miles-core/src/miles_core/infra/db/async_session.py:79-82` 的 `get_worker_session()`
用裸 `create_async_engine(settings.database_url, echo=..., pool_pre_ping=True)`，**绕过
`build_engine`** ⇒ worker engine 静默忽略 `db_pool_size` / `db_max_overflow` / `db_pool_timeout`
（当前值恰为默认值故无症状，一旦有人调参就会静默漂移）。改为经 `build_engine` 构造，并补测试
断言 worker engine 的池参数与配置一致。

- [ ] **Step 4（Minor）修正 `get_worker_session()` docstring 的归因**

`:67` 现称「Fork 后父进程的全局 engine 内部 asyncpg 连接残留了旧事件循环的 Future」。实测
机制是**同一进程内每次 `asyncio.run` 换新 loop**：连续 6 次调用在第 2/4/6 次失败，与 fork
无关（fork 场景只是更早暴露）。改为如实描述 per-task loop churn。

- [ ] **Step 5（Minor）修正 spec §10 的过度声明与计数不一致**

spec `:270,:273,:377` 称本分支「已修」`progress.py`，但 **`progress.py` 在基点
（`4ba6ce5f`）就已经是 `short_db_session`**（它是上一分支重命名时迁过去的），本分支对它的
**生产代码零改动**，只补了护栏与清单登记。改为如实表述：本分支修的是「因 Worker 可达而
**缺护栏**」的站点，其中 `progress.py` 属于「本就安全但漏了护栏与清单登记」。

同时统一三处不一致的计数（计划 10/12、spec 11/14、测试清单 13）为同一口径，并说明各数字各自
的含义（Task 1 触碰 12 处/10 文件；须受护栏保护的 Worker 可达模块 13 个）。

**落地结果**：统一后的口径表在 spec §10.4（10 文件/12 处 = 本分支 `git diff` 实际改动；
11 文件/14 处 = 该节表枚举的 Worker 同险站点总数，含基点即安全的 `progress.py` 2 处；
13 模块 = 须受 §10.5 护栏保护的模块数）。本文件 `:262` 是 Task 3 已执行提交的消息正文，
属历史记录，不改。

- [ ] **Step 6（Minor）交叉核对改用 AST，消除注释假阳性**

复现：`sync.py` 里一行含 `short_db_session()` 的**注释**即触发「清单缺项」。Task 3 选择「让
docstring 如实描述」而非消除假阳性，终审判为仍留坑。Step 1 既然已改用 AST，此处一并对齐
（注释/字符串不再计入）。

- [ ] **Step 7：门禁 + 两次提交**

五条门禁全绿（预期 1082 + 新增护栏数，warnings 仍恰为 2）。拆两枚提交：
生产改动（Step 1–4 中涉及 `async_session.py` 的部分）与测试/文档改动分开。

**不做（明确 defer，记入 spec）：** 终审 Important-3 建议在 Celery 边界做**结构性**修复——
仓库已为 Redis 解决过同类问题（`get_redis()` 按 loop id 重建），DB 亦可仿此让 engine 随 loop
重建，从而一次性覆盖全部站点（含既有排除项与未来新站点），而不必依赖「每处记得选对工厂」的
惯例。该改动动核心基础设施（旧 engine/池的释放与生命周期），风险与本分支范围不符，另立专项；
本分支的护栏可作为结构修复落地前的纵深防御。
