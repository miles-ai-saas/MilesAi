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

**生成阶段不长时间占连接：** 外部 IO（LLM、Peer HTTP、厂商 API）前应尽量 `await session.commit()`，释放请求/Worker 事务占用的连接；IO 结束后再开短会话写回。取会话一律走上述工厂，勿自建全局 `engine` / 旧式 `get_worker_session` / `short_db_session`（已收敛删除）。

## commit-before-IO 路径盘点

**已对齐**（读装配完成后 commit，再进入慢 IO）：

| 路径 | 代码锚点 |
|------|----------|
| Agent 直连 / RAG | `miles_portal/.../agent/chat_rag.py`（`direct_chat`、RAG 检索后 `ainvoke_chat` 前） |
| 发布 Flow 跑图 | `miles_portal/.../agent/chat_entry.py`（`_run_published_flow`，`flow_run_context` 后、`run` 前） |
| A2A 宿主 | `miles_portal/.../a2a/invoke.py`（`run_a2a_host_chat`：Peer HTTP / 编排 LLM 前） |
| 模型健康探测 | `miles_worker/.../model_health.py`（load 会话关闭 / 释放连接后探测，写回另开会话） |

**尚未对齐**（仍可能在长 IO 期间持有同一会话）：

- `tool_agent` 工具循环与 `SessionMediaReader`
- KB ingest（embedding / 向量写入等分阶段事务）
- Generative Worker 内厂商调用仍包在同一 DB 会话
- A2A：`resolve_a2a_plan_items` 内的规划 LLM（`plan_a2a_peers`）发生在 host 路径 commit 之前

更完整的骨架说明见 [backend-reference-framework.md](../architecture/backend-reference-framework.md) 中 `infra/db` 段落。
