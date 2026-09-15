# Loop 感知的 DB 引擎与会话工厂（结构修复）

- 状态：设计待评审
- 日期：2026-09-15
- 前序：`2026-09-14-rag-generation-db-connection-design.md`（该文 §10.5 将本设计记为 Important-3「结构性修复」，另立专项）

## 1. 问题

Celery 任务入口用 `asyncio.run(...)`，**每次调用新建一个事件循环**。而 `miles_core.infra.db` 的
`engine` 是模块级单例，其连接池里可能仍留着上一个 loop 创建的 asyncpg 连接：新 loop 里第一次
复用该连接即抛

```
RuntimeError: got Future attached to a different loop
```

实测（真库、同一进程连续 6 次 `asyncio.run`）：全局会话在第 2/4/6 次失败，约一半。

前两个分支已为此打了**按站点**的补丁：`get_worker_session()` 在 worker 任务内新建 engine 并把
sessionmaker 绑到 `ContextVar`，13 个模块改用 `short_db_session()` 取会话。

该补丁能工作，但有三个结构性问题：

1. **可选加入，漏了就坏。** 只要有一个从 Worker 可达的站点仍直接 `AsyncSessionLocal()`，它就
   照旧失败；而「某个站点是否在 Worker 子树里」是靠人判断的，没有机制保证不漏。
2. **每个站点都要自己知道自己在哪。** 「选对工厂」是调用点的责任，属于最容易腐化的形状——
   已经腐化过一次（`progress.py` 漏过一轮护栏与清单登记）。
3. **正确性依赖调用点的正确性，而非基础设施的自洽。** 同一件事（拿会话）有两套 API
   （`AsyncSessionLocal()` 与 `short_db_session()`），语义差别只存在于文档与护栏里。

## 2. 现状

| 符号 | 现状 |
|---|---|
| `engine` | 模块级 `AsyncEngine` 单例（`build_engine(settings)` 构造） |
| `AsyncSessionLocal` | 模块级 `async_sessionmaker` 实例；仓内**只被当函数调用**（`AsyncSessionLocal()`） |
| `get_worker_session()` | `@asynccontextmanager`；worker 内新建 engine + 绑定 `_worker_sessionmaker` ContextVar，退出时 `reset` + `engine.dispose()` |
| `short_db_session()` | 有 worker 绑定时用绑定的 maker，否则回退 `AsyncSessionLocal` |
| `get_db()` | FastAPI 请求级会话；形状不受本设计影响 |

调用面（已核查）：

- `short_db_session()` 使用者：**13 个模块 / 13 个文件 / 18 处调用点**（见 §6.1 逐处清单）。
- `get_worker_session()` 使用者：1 处，`miles_worker/tasks/agent_schedule.py:34`。
- `engine` 直接使用者：1 处，`miles_core/utils/health_checks.py:13`（`:36` 处 `engine.connect()`）。
- Worker 侧异步入口（`asyncio.run`）共 3 个：
  `tasks/generative.py` 的 `_run_coro`（`:22` 定义，`:26` 的 `asyncio.run`）、
  `tasks/agent_schedule.py:84`、`tasks/model_health.py:71`。
  `tasks/ingest.py` 走**同步**引擎（`get_sync_db`），不受本设计影响。
- Redis 侧已有同类先例：`infra/redis/client.py` 的 `get_redis()` 按 loop 重建客户端，
  `reset_redis()` 由 `tasks/generative.py:28` 在 `asyncio.run` **之后**调用。

## 3. 设计目标

1. **让 `AsyncSessionLocal()` 自身 loop 感知**：调用方写法与今天完全一致，无需知道自己在
   Worker、API 还是脚本里。结构上消除「选错工厂」这一整类错误。
2. **所有经 `asyncio.run` 的路径都拿到当前 loop 的 engine**，含既有被排除站点与未来新站点。
3. **不留连接泄漏**：每次 `asyncio.run` 换 loop ⇒ 每个任务一个新 engine，旧 engine 的池必须
   在 **loop 关闭前** 被释放。
4. **删除按站点机制**：`get_worker_session()`、`short_db_session()`、`_worker_sessionmaker`
   ContextVar 与相关护栏一并移除，只留一个概念。

## 4. 非目标

- **不改 Redis。** `get_redis()` / `reset_redis()` 保持原样，且**不并入** DB 的释放路径：DB 的
  释放是正确性要求（必须在 loop 关闭前 `await`），Redis 的 reset 只是尽早放手（`get_redis()`
  自愈，不调也不错）。两者语义不同，不共用 helper。
  另记：`get_redis()` 用 `id(loop)` 作键，存在 loop 对象被回收后 id 复用的隐患——本设计不复制
  该做法，但也不在本专项修它。
- **不合并 `FlowMediaReader` 与 `SessionMediaReader`。** 其区分是**事务归属**（是否复用调用方
  事务），不是 loop 安全；两者都保留。
- **不处理 tool agent / a2a 持请求会话**：属另一专项。
- **不动 `get_db()`**：FastAPI 单长命 loop 下行为不变。
- **不引入依赖。**

## 5. 方案

### 5.1 核心机制：按 loop 缓存 engine + sessionmaker

`async_session.py` 里以 **loop 对象**为键注册每 loop 的 `(engine, sessionmaker)`：

```python
_loop_engines: WeakKeyDictionary[AbstractEventLoop, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = (
    WeakKeyDictionary()
)

def _loop_engine_and_maker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """取当前 loop 的 (engine, sessionmaker)；缺失则用 build_engine() 懒建并登记。"""
    loop = asyncio.get_running_loop()  # 无运行 loop 时抛 RuntimeError，属预期
    entry = _loop_engines.get(loop)
    if entry is None:
        engine = build_engine(settings)
        entry = (engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False))
        _loop_engines[loop] = entry
    return entry

def get_engine() -> AsyncEngine:
    """当前事件循环的 engine（懒建）。"""
    return _loop_engine_and_maker()[0]

def AsyncSessionLocal() -> AsyncSession:
    """当前事件循环的会话（签名与旧 sessionmaker 调用一致）。"""
    return _loop_engine_and_maker()[1]()

async def dispose_loop_engines() -> None:
    """释放**当前 loop** 的 engine（由 worker 边界在关闭 loop 前调用）。

    幂等：无条目或已释放时为空操作。释放是 ``pop`` 整条注册项，故同一 loop 再取会话会**新建一个
    engine**（新池，由同一 ``Settings`` 快照重建），而不是复用已释放的旧池。
    """
```

要点：

- **键用 loop 对象本身（`WeakKeyDictionary`），不用 `id(loop)`**。这避免了 Redis 先例的 id 复用
  隐患——已释放 loop 的条目不可能被新 loop 误命中。
  **注意：弱键不提供自动清理。** 实现阶段已实测确认：`asyncpg` 连接强引用 loop
  （`asyncpg/connection.py:65` 的 `self._loop = loop`），池又强持有连接（`asyncpg/pool.py:343,454`），
  而注册表对 value（engine）持强引用，故「注册表 → engine → 池 → 连接 → loop」会把 weak key 钉住：
  只要池里还有存活连接，条目永不失效。因此**唯一的释放路径是显式 `dispose_loop_engines()`**，
  由 Worker 边界（§5.3）与终检实测的泄漏观察一起兜住；不能把它当作可选优化。
- **`AsyncSessionLocal()` 调用写法不变**（返回 `AsyncSession`、`expire_on_commit=False`），故
  既有测试里「按模块属性名打桩」的写法继续可用（新符号仍是模块级名字）。
- **无运行 loop 时抛 `RuntimeError`**，比今天「等到 await 才炸」更早暴露。已核查仓内调用点全部
  位于 async 函数内。
- `build_engine(settings)` 保留，由注册表内部调用（测试仍可直接构造引擎）。

### 5.2 符号收敛

| 符号 | 处置 |
|---|---|
| `engine` | **删除** → `get_engine()`；唯一消费者 `health_checks.py:13` 改用之，`infra/db/__init__.py` 的导入与 `__all__` 同步 |
| `AsyncSessionLocal` | `sessionmaker` 实例 → 模块级**函数**；调用点写法不变 |
| `get_worker_session()` | **删除**；`agent_schedule.py:34` 改用 `AsyncSessionLocal()` |
| `short_db_session()` | **删除**；13 个模块改回 `AsyncSessionLocal()`（见 §6） |
| `_worker_sessionmaker` / `_set_worker_sessionmaker` / `_reset_worker_sessionmaker` | **删除** |
| `build_engine` / `get_db` | 保留，形状不变 |

> 注：`engine` 是公开导出符号，删除会波及 `miles_core.infra.db.__all__`。这是用户选定「单一
> 工厂」方案的应有之义（收敛而非并存），执行时同步更新导出。

### 5.3 Worker 边界：在 loop 关闭前释放

新增**只负责 DB** 的边界包装（命名直说与 DB 相关，避免日后被塞入 Redis）：

```python
# miles_core/infra/db/async_session.py
def run_worker_db_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """Worker 入口用：跑 coro，并在**关闭 loop 之前**释放本 loop 的 engine。

    释放必须发生在 loop 关闭前——``engine.dispose()`` 是协程，loop 关了就无法 await；
    而每次 ``asyncio.run`` 换 loop，不释放就会每个任务泄漏一池连接。
    """
    async def _main() -> Any:
        try:
            return await coro
        finally:
            await dispose_loop_engines()

    return asyncio.run(_main())
```

3 个异步 Celery 入口改用它：

| 入口 | 现状 | 改为 |
|---|---|---|
| `tasks/generative.py:22` `_run_coro` | `try: asyncio.run(coro) finally: reset_redis()` | `run_worker_db_coro(coro)`；`reset_redis()` 是否保留见下 |
| `tasks/agent_schedule.py:84` | `asyncio.run(_run_schedule_async(...))` | `run_worker_db_coro(_run_schedule_async(...))` |
| `tasks/model_health.py:71` | `return asyncio.run(_probe_models_async())` | `return run_worker_db_coro(_probe_models_async())` |

- **Redis 不进这个 helper。** `generative._run_coro` 里现有的 `reset_redis()` 保持原样（它是
  Redis 自己的清理，`get_redis()` 自愈故漏了也不错）；另两个入口不新增 `reset_redis()`。
- **CLI 脚本不改**（`db_ops` / `verify_db` / `backfill_media_assets`）：单次进程只跑一个 loop，
  进程退出即释放。

### 5.4 数据流

API（uvicorn 单长命 loop）：
`AsyncSessionLocal()` → 注册表命中该 loop → 首次懒建 engine（`build_engine`）→ 后续复用。

Worker（每任务一个 loop）：
`run_worker_db_coro(coro)` → `asyncio.run` 建 loop → 任务体内任意
`AsyncSessionLocal()` 命中**本 loop** 的 engine → 任务结束 → `finally` 里
`await dispose_loop_engines()` 释放该 engine → loop 关闭。

## 6. 语义变化

### 6.1 调用点回退（13 个模块 / 13 个文件 / 18 处）

`short_db_session()` → `AsyncSessionLocal()`，import 同步：

| 模块 | 站点 |
|---|---|
| `miles_ai/integrations/langgraph/graphs/rag_qa.py` | `:67` |
| `miles_ai/integrations/generative/jobs/progress.py` | `:54`、`:75` |
| `miles_ai/flow_runtime/nodes/rag_nodes.py` | `:48` |
| `miles_ai/flow_runtime/nodes/image_generate.py` | `:55`、`:84` |
| `miles_ai/flow_runtime/nodes/video_generate.py` | `:56`、`:86` |
| `miles_portal/tenant/models/services/usage.py` | `:128`、`:167` |
| `miles_portal/tenant/agents/services/agent/chat_rag.py` | `:382` |
| `miles_portal/tenant/attachments/services/media_reader.py` | `:44`、`:50` |
| `miles_portal/tenant/tools/services/flow_invoker.py` | `:40` |
| `miles_portal/tenant/flows/services/run_context.py` | `:25` |
| `miles_portal/tenant/flows/services/subflow_loader.py` | `:25` |
| `miles_portal/tenant/prompts/services/template_loader.py` | `:42` |
| `miles_portal/tenant/compliance/services/scan_words_loader.py` | `:24` |

行为不变之处：这些站点本就要求「独立于调用方事务的短会话」，`AsyncSessionLocal()` 依旧每次返回
**新** 会话，语义等同。

### 6.2 自动变安全（无需改动）

此前被排除在护栏外的 5 个站点现在自动获得 loop 安全，无需任何改动：

- `miles_core/risk/enforce.py:42,87`
- `miles_portal/tenant/agents/ws/chat.py:114,160,185`
- `miles_portal/tenant/agents/ws/job_watch.py:72`
- `miles_server/scripts/backfill_media_assets.py:97`、`db_ops.py:58,69`

### 6.3 不再存在的概念

`short_db_session` 与 `get_worker_session` 从代码、文档与护栏中消失。「这个站点要不要用短会话」
「我在不在 Worker 里」不再是调用点需要回答的问题。

## 7. 测试策略

**旧护栏大半失效，须重构而非叠加。** 现有 20 个测试文件引用 `AsyncSessionLocal`，其中：

- 13 个站点的 `_Boom` + `short_db_session` 打桩机件**删除**（新设计里没有「选错工厂」这个错误，
  站点用的就是普通 `AsyncSessionLocal()`）。这些文件回退为「打桩 `AsyncSessionLocal` 注入假
  会话」的普通脚手架。
- `tests/infra/test_no_global_session_in_worker_paths.py`（13 模块清单 + AST allowlist）与
  `tests/infra/test_worker_session_composition.py`（块内/块外工厂身份）**解散**——它们守护的
  「谁可以碰全局会话」概念不复存在。
- `tests/infra/test_short_db_session.py` **删除**（被守护的 helper 消失）。

**换守护新不变量**（均为 hermetic 测试）：

1. **跨 loop 不复用**：loop A 取一次会话、loop B 再取一次，断言两者来自**不同** engine
   （打桩 `build_engine` 记录 `(loop_id, engine)`）。这是本 bug 的本质。
2. **`dispose_loop_engines()`**：只释放**当前** loop、可重复调用；释放后同一 loop 再取会话**仍可用**
   ——释放是 `pop` 整条注册项，故下次取会话是**新建一个 engine**（新池，由同一 `Settings` 快照重建），而非复用空池。
3. **边界包装在 loop 关闭前完成释放**：以记录器替换 `dispose_loop_engines`，断言调用时**确有
   运行中的 loop**；异常路径同样释放，且异常照常传播。
4. **真库端到端**：连续 6 次经包装跑真实的 DB 站点，断言 6/6 成功；并以「绕过注册表、固定复用
   同一个全局 engine」的对照组证明探针**敏感**（该对照组复现旧行为，应出现约半数失败）。
5. **接线不变量**：`health_checks` 走 `get_engine()`、`infra/db/__init__.py` 不再导出已删符号。

门禁同前：`ruff format --check .`、`ruff check .`、`lint-imports`、
`python -m miles_server.scripts.export_openapi --check`、`python -m pytest -q`
（main 基线 1090 passed；全量计数随本分支各任务推进递增，warning 数按最近一次全量 run 实测，不在此写死——
不同 `-W` 过滤器下数字不同，写死只会制造假精确）。

> 测试环境事实（已核查）：`pytest-asyncio` 为 `asyncio_mode = "auto"`，未配置 `loop_scope`
> ⇒ 每个用例一个新 loop，因此「按 loop 缓存 engine」在测试里不会跨用例复用；`tests/conftest.py`
> 把 `get_db` 覆盖为 `AsyncMock`，故现有用例不触真库。

## 8. 风险

| 风险 | 评估与对策 |
|---|---|
| 每个任务新建 engine 的开销 | 与现状（`get_worker_session()` 每任务新建 engine）相同，不新增开销 |
| 连接泄漏（忘记释放） | 由 `run_worker_db_coro` 集中保证；漏掉释放的入口会随任务数累积。列为 §7.3 的不变量测试；另在实现时实测「6 次连续任务后的连接数」 |
| `WeakKeyDictionary` 以 loop 为键 | 需确认常见 loop 实现（标准 asyncio、uvloop）可弱引用；实现阶段以一条小测试钉住，若不可弱引用则退化为按 `id(loop)` 加存活校验。**已确认**：标准 asyncio loop 可弱引用（仓内未用 uvloop） |
| 删 `engine` 是破坏性导出变更 | 仓内唯一消费者 `health_checks.py` 已定位；实现时以 `rg` 复扫确认，并跑全量门禁。**已完成** |
| uvicorn 单长命 loop 下条目常驻 | 正确行为（本就该复用）；该 loop 的 engine 由其自身生命周期覆盖，无需跨 loop 释放 |
| 弱键不提供自动清理（实现阶段实测修正） | `asyncpg` 连接强引用 loop、池强持有连接，注册表持强引用的 engine 反钉 weak key ⇒ **只要有存活连接，条目永不失效**。故 `dispose_loop_engines()` 是唯一释放路径，不是可选优化；已同步改正第 5 节与代码 docstring。**终检实测**：漏掉释放时，6 次连续任务后注册表条目 0→6、数据库连接数 0→6（严格线性），同一批量在 `run_worker_db_coro` 下两项均为 0 |
| 复用旧 loop 的 engine 不会被 `pool_pre_ping` 悄悄治愈（终检实测） | 对照实验把 engine 固定复用第一次 loop 那份（等价迁移前的模块级单例），6 次任务失败 3 次（第 2/4/6 次），异常为 `RuntimeError: Task ... got Future <Future pending ...> attached to a different loop`：抛出点是**池检出时的 pre-ping**（`sqlalchemy/pool/base.py:1309` → `asyncpg.py:825 _async_ping`），经 `util.safe_reraise()` 一路冒到 `progress.update_generative_job_progress` 的 `db.get()`——即 `build_engine()` 里那个 `pool_pre_ping=True` 并未把它判成普通断连后静默换连接。结论：该池开关不会掩盖本 bug，回归一旦发生是响的（不会退化成「偶发慢」这类软故障）；代价是失败的任务会在进程存活期间留下 `idle in transaction` 服务端连接（终检探针实测 3 次失败留下 2 条，即 `after_B=2`；进程退出后消失），且 asyncio 会为已关闭 loop 上的连接终止补打 `RuntimeError: Event loop is closed` 例外日志 |
| 同一 loop 内 dispose 后再取会话 | `pop` 掉整条 `(engine, maker)` 后，下次 `AsyncSessionLocal()` 会**新建整个 engine**（含新池，由同一 `Settings` 快照重建），而非复用空池 |
| dispose 失败会顶掉任务异常（**已接受，不改代码**） | 现象：`finally: await dispose_loop_engines()` 若 dispose 自身抛错，它会替换 `try` 里的业务异常成为主异常，业务异常降级为 `__context__`。接受理由：调用方是 Celery 任务，「清理失败」让任务失败并暴露出来，比静默泄漏更容易被发现；信息未丢失（异常链上仍在），代价只是排查首因要多看一层。将来若确需改：在 `finally` 里 `try/except` 包住 dispose（清理失败只 `logger.exception` 记录，不顶掉业务异常）——会引入分支，收益与「dispose 自身抛错」这一低概率事件不匹配，故不做 |

## 9. 遗留

- `get_redis()` 的 `id(loop)` 复用隐患（本设计不复制该做法，但不在本专项修）。
- tool agent / a2a 路径持请求会话（另一专项）。
- `SessionMediaReader` / `FlowMediaReader` 的并存（事务归属语义，保留）。

## 10. 修订记录

- 2026-09-15 首版：确立「单一 loop 感知工厂」终局形态；经用户确认——① 采「单一工厂」而非
  「分层保留」；② engine 释放归 Worker 边界统一包装（`run_worker_db_coro`）；③ 工厂以模块级
  **函数**实现；④ **DB 与 Redis 解耦**，Redis 不并入该 helper。

- 2026-09-15 终检（Task 4，**不改任何代码**）：已实施并全量复验。五条门禁全绿
  （`ruff format --check .` / `ruff check .` / `lint-imports`（6 contracts kept, 0 broken）/
  `export_openapi --check` / `python -m pytest -q`）；全量 **1076 passed**，默认过滤器下无
  warnings summary，同一 `-W default` 过滤器下 5 条既有 ResourceWarning（redis 连接未关 ×4、
  loop 未关 ×1）与基线同数，**无新增**。真库端到端探针 6/6 成功、敏感性对照 3/6 失败、连接数
  不随任务数增长（明细见下）。

  **① 测试数口径为何是 1076 而非计划里的 1077。** Task 3 除计划内的两处删减外，还删掉了
  `tests/tenant/attachments/test_flow_media_reader.py::test_module_does_not_reference_global_session_factory`
  ——它的断言 `not hasattr(media_reader_mod, "AsyncSessionLocal")` 被「模块内必有该工厂」这一迁移
  事实必然为假，删掉比反写成恒真式更诚实（Task 3 评审认可）。故实测比计划口径少 1。

  **② Task 3 另有两处计划外但经评审认可的处置，如实补记。** (a) **退役整个**
  `tests/infra/test_no_global_session_in_worker_paths.py`：6 个测试函数、参数化后 19 条，守护的
  「13 模块清单 + AST allowlist」概念在 §6.3 之后不复存在，改写成新概念下的等价物即制造第二份
  §7 清单，故解散。(b) **重命名 14 条仍在描述旧机制的护栏用例**（旧名里的
  `never_falls_back_to_global_session` / `uses_short_session` / `within_short_session` 描述的是已经
  删掉的「选错工厂」错误；断言本身已改为「在自己那份会话上跑」）。14 条逐条如下，写进修订记录是
  为了让「改名」与「删测试」在后续 review 里可被区分，避免被误读为覆盖度下降：

  | 文件 | 旧名 → 新名 |
  |---|---|
  | `tests/flow/test_generative_nodes.py` | `test_image_generate_sync_never_falls_back_to_global_session` → `test_image_generate_sync_honours_injected_resolver_and_orchestrator` |
  | 同上 | `test_video_generate_sync_never_falls_back_to_global_session` → `test_video_generate_sync_honours_injected_resolver_and_orchestrator` |
  | `tests/flow/test_prompt_template_node.py` | `test_knowledge_search_never_falls_back_to_global_session` → `test_knowledge_search_retrieves_on_its_own_session` |
  | `tests/rag/test_rag_qa_nodes_share_generate.py` | `test_retrieve_node_uses_short_session_not_global` → `test_retrieve_node_retrieves_on_its_own_session` |
  | `tests/tenant/compliance/test_scan_words_loader.py` | `test_loader_delegates_with_short_session_and_tenant` → `test_loader_delegates_with_own_session_and_tenant` |
  | 同上 | `test_loader_never_falls_back_to_global_session` → `test_loader_reads_words_from_its_own_session` |
  | `tests/tenant/flows/test_run_context_session.py` | `test_model_resolver_never_falls_back_to_global_session` → `test_model_resolver_runs_inside_its_own_session` |
  | 同上 | `test_model_resolver_missing_model_reports_bad_request_within_short_session` → `test_model_resolver_missing_model_reports_bad_request_within_its_own_session` |
  | `tests/tenant/flows/test_subflow_loader.py` | `test_subflow_loader_never_falls_back_to_global_session` → `test_subflow_loader_builds_repository_on_its_own_session` |
  | `tests/tenant/generative/test_progress_session.py` | `test_update_progress_never_falls_back_to_global_session` → `test_update_progress_writes_and_publishes_on_its_own_session` |
  | 同上 | `test_is_cancelled_never_falls_back_to_global_session` → `test_is_cancelled_reads_on_its_own_session` |
  | `tests/tenant/models/test_flow_usage_sink.py` | `test_flow_usage_sink_record_never_falls_back_to_global_session` → `test_flow_usage_sink_record_writes_one_submitted_row` |
  | `tests/tenant/prompts/test_template_loader.py` | `test_loader_never_falls_back_to_global_session` → `test_loader_loads_live_reference_from_its_own_session` |
  | `tests/tenant/tools/test_flow_invoker_session.py` | `test_flow_tool_invoker_never_falls_back_to_global_session` → `test_flow_tool_invoker_runs_on_its_own_session` |

  （14 条均已核对：旧名在 `HEAD` 的 `backend/tests` 里零命中、新名只在 `HEAD` 出现。）

  **③ 真库端到端探针（`/tmp/task4_loop_probe.py`，不提交）三组结果。**

  - **组 A（正例）**：连续 6 次 `run_worker_db_coro(...)`，每次在协程内跑 3 个真实站点——
    `progress.update_generative_job_progress`（`AsyncSessionLocal()` + `db.get(GenerativeJob)` +
    `commit`）、`langgraph/graphs/rag_qa.py::retrieve`（`AsyncSessionLocal()` + `kb_bases` 真实
    SELECT + Milvus 检索）、`prompts/services/template_loader.py` 的 loader 闭包
    （`db.get(PromptTemplate)`）。**6/6 成功**；6 个 loop 互不相同、6 个 engine 互不相同
    （`distinct_loops=6`、`distinct_engines=6`），每次跑完注册表条目回到 0。
  - **组 B（跨 loop 敏感性对照）**：把 `_loop_engine_and_maker` 换成「engine 建一次、所有 loop
    复用」，等价迁移前的模块级单例。**3/6 失败，恰为第 2/4/6 次**，异常全部是
    `RuntimeError: Task ... got Future <Future pending ...> attached to a different loop`；逐帧
    traceback 显示抛出点是**池检出时的 pre-ping**（`sqlalchemy/pool/base.py:1309` →
    `asyncpg.py:825 _async_ping` → `asyncpg/connection.py:354`），再经 `util.safe_reraise()`
    冒到 `miles_ai/integrations/generative/jobs/progress.py:55` 的
    `job = await db.get(GenerativeJob, job_id)`——即复用的连接在第一次 await 上炸，且该
    `RuntimeError` **没有**被 `pool_pre_ping` 当成普通断连吞掉。没有这组，「6/6 成功」无法排除
    「探针根本没触到跨 loop 路径」。
  - **组 C（连接计数的敏感性对照）**：保留 loop 感知注册表，但用裸 `asyncio.run` 起 loop（等价
    「忘了在 loop 关闭前释放」）。**6/6 成功，但注册表条目 0→6、连接数 0→6（严格线性）**——这既
    给组 A 的「0 增长」提供了判别力证明（不是连接被别的东西顺手关掉了），也是 §8「弱键不自动
    清理」那条的实测证据。
  - **连接数口径**：`pg_stat_activity` 按 `datname = current_database()` + `usename = current_user`
    过滤，排除计数器自身那条连接（`application_name = 'task4_probe_counter'`）。四个观测点：
    `baseline = 0` → `after_A = 0` → `after_B = 2`（对照组 3 次失败留下 2 条 `idle in transaction`
    残连，进程存活期间可见）→ `after_C = 6`；清理后 `final = 0`。**组 A 的增量是 0，不随任务数增长。**
  - **夹具与清理（全部完成，可复核）**：探针插入 1 条 `generative_jobs`（`progress_percent` 复核为
    60、`progress_message = 'task4 probe run 6'`，证明 6 次写入真的落到库里）与 1 条
    `kb_bases`（探针专用，`retrieval_mode='vector'`、dim 1024）；`finally` 中按 id 删除，
    `rowcount` 各 1、残留 0。探针在 Milvus 上创建的空 collection `document_chunk_1024` 用完即
    drop（`before = []`、`after = []`）。组 B/C 造出的 6 条服务端连接用 `pg_terminate_backend`
    掐掉（6/6 返回 True）。结束时库中无残留行、无残留 collection、连接数回到 baseline。
  - **探针与生产的差异（如实记录，非「造假」）**：向量后端在 settings 里默认为 `weaviate`（本机
    8080 未启动），探针进程内改用 `VECTOR_STORE_BACKEND=milvus`（docker 中真实在跑的后端）；
    embedding 回调用固定向量替身（本机无 `DASHSCOPE_API_KEY`，`agt_model_tenant_credentials`
    亦为空表，真实 provider 调用必失败），但**DB 路径本身（会话创建 + `kb_bases` 查询）未打桩**，
    组 B 的失败点恰好落在 `db.get()` 上，可证跨 loop 路径确被触到。

  **④ `WeakKeyDictionary` 修正（必须记录）。**

  > 第 5 节原称「`WeakKeyDictionary` 的弱键让 loop 回收即自动摘除」——实施后实测证明该说法
  > 错误（asyncpg 连接强引用 loop、池强持有连接、注册表强引用 engine ⇒ 条目被钉住，只要有存活
> 连接就永不失效）。已改为「弱键只规避 `id(loop)` 复用，**唯一释放路径是显式
> `dispose_loop_engines()`**」，§5 与 §8 均已同步；代码 docstring 同。

  **⑤ 非目标复核（未误改）。** `git diff main...HEAD --stat` 共 45 个文件，全部落在 DB 会话、
  Worker 入口、§6.1 的 18 处调用点与其测试、以及本 spec/plan 文档内：不含
  `miles_core/infra/redis/` 任何文件（Redis 侧零改动）；`media_reader.py` 的差异只有
  `short_db_session()` → `AsyncSessionLocal()` 与两处 docstring 措辞，`FlowMediaReader` /
  `SessionMediaReader` 的「事务归属」区分未动；无 tool agent / a2a 路径文件；`get_db()` 形状
  不变（仅会话来源变化）。`rg -n "from miles_core.infra.redis"
  packages/miles-core/src/miles_core/infra/db/` 零命中，§4 的「DB 层不依赖 Redis」成立。
  §8 新增一条「`pool_pre_ping` 不会悄悄治愈本 bug」的实测结论。
