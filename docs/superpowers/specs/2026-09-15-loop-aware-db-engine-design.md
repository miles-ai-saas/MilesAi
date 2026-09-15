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

    幂等：无条目或已释放时为空操作。释放后同一 loop 再取会话会在下次连接时惰性重建池。
    """
```

要点：

- **键用 loop 对象本身（`WeakKeyDictionary`），不用 `id(loop)`**。这避免了 Redis 先例的 id 复用
  隐患，且 loop 被回收时条目自动消失。
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
2. **`dispose_loop_engines()`**：只释放**当前** loop、可重复调用；释放后同一 loop 再取会话仍可用
   （SQLAlchemy 会在下一次连接时惰性重建池）。
3. **边界包装在 loop 关闭前完成释放**：以记录器替换 `dispose_loop_engines`，断言调用时**确有
   运行中的 loop**；异常路径同样释放，且异常照常传播。
4. **真库端到端**：连续 6 次经包装跑真实的 DB 站点，断言 6/6 成功；并以「绕过注册表、固定复用
   同一个全局 engine」的对照组证明探针**敏感**（该对照组复现旧行为，应出现约半数失败）。
5. **接线不变量**：`health_checks` 走 `get_engine()`、`infra/db/__init__.py` 不再导出已删符号。

门禁同前：`ruff format --check .`、`ruff check .`、`lint-imports`、
`python -m miles_server.scripts.export_openapi --check`、`python -m pytest -q`
（当前基线 1090 passed / 2 既有 warning）。

> 测试环境事实（已核查）：`pytest-asyncio` 为 `asyncio_mode = "auto"`，未配置 `loop_scope`
> ⇒ 每个用例一个新 loop，因此「按 loop 缓存 engine」在测试里不会跨用例复用；`tests/conftest.py`
> 把 `get_db` 覆盖为 `AsyncMock`，故现有用例不触真库。

## 8. 风险

| 风险 | 评估与对策 |
|---|---|
| 每个任务新建 engine 的开销 | 与现状（`get_worker_session()` 每任务新建 engine）相同，不新增开销 |
| 连接泄漏（忘记释放） | 由 `run_worker_db_coro` 集中保证；漏掉释放的入口会随任务数累积。列为 §7.3 的不变量测试；另在实现时实测「6 次连续任务后的连接数」 |
| `WeakKeyDictionary` 以 loop 为键 | 需确认常见 loop 实现（标准 asyncio、uvloop）可弱引用；实现阶段以一条小测试钉住，若不可弱引用则退化为按 `id(loop)` 加存活校验 |
| 删 `engine` 是破坏性导出变更 | 仓内唯一消费者 `health_checks.py` 已定位；实现时以 `rg` 复扫确认，并跑全量门禁 |
| uvicorn 单长命 loop 下条目常驻 | 正确行为（本就该复用）；loop 回收后由弱引用自动清理 |
| 同一 loop 关闭后条目短暂滞留（GC 前） | 仅影响稳态内存，量级为「一个已释放 engine 的包装对象」；由边界 `finally` 覆盖正常路径 |

## 9. 遗留

- `get_redis()` 的 `id(loop)` 复用隐患（本设计不复制该做法，但不在本专项修）。
- tool agent / a2a 路径持请求会话（另一专项）。
- `SessionMediaReader` / `FlowMediaReader` 的并存（事务归属语义，保留）。

## 10. 修订记录

- 2026-09-15 首版：确立「单一 loop 感知工厂」终局形态；经用户确认——① 采「单一工厂」而非
  「分层保留」；② engine 释放归 Worker 边界统一包装（`run_worker_db_coro`）；③ 工厂以模块级
  **函数**实现；④ **DB 与 Redis 解耦**，Redis 不并入该 helper。
