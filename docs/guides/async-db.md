# 异步 DB 会话（loop 感知）

> 类型：实现说明 | 状态：已实现 | 代码：`miles_core.infra.db.async_session`

## 现行约定

| 入口 | 用途 |
|------|------|
| `AsyncSessionLocal()` | 取**当前事件循环**的会话（与旧 `sessionmaker()` 写法兼容） |
| `get_db()` | FastAPI 请求级：正常 `commit`，异常 `rollback` |
| `run_worker_db_coro(coro)` | Celery / Worker：`asyncio.run` 包一层，在 **loop 关闭前** `dispose_loop_engines()` |
| `dispose_loop_engines()` | 释放当前 loop 的 engine（幂等） |

**为什么按 loop 持有 engine：** Celery 任务每次 `asyncio.run` 都新建 loop；复用绑在旧 loop 上的 asyncpg 池会抛 `got Future attached to a different loop`。注册表以 loop 对象为键（`WeakKeyDictionary`），条目须显式 dispose，不能依赖弱引用自动回收。

**生成阶段不长时间占连接：** Agent RAG / 生成链路在调 LLM 前结束业务会话（或只在短临界区读写），避免池被慢调用占满。取会话一律走上述工厂，勿自建全局 `engine` / 旧式 `get_worker_session` / `short_db_session`（已收敛删除）。

更完整的骨架说明见 [backend-reference-framework.md](../architecture/backend-reference-framework.md) 中 `infra/db` 段落。
