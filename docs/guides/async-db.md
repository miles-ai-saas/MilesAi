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

**已对齐**（读装配完成后 commit，再进入慢 IO；写回可用同一 Session，`expire_on_commit=False`）：

| 路径 | 代码锚点 |
|------|----------|
| Agent 直连 / RAG | `miles_portal/.../agents/services/agent/chat_rag.py`（`direct_chat`、RAG 检索后 `ainvoke_chat` 前） |
| `tool_agent` 多轮循环 | 同上 `_run_tool_agent`（`assemble_agent_tools` 后 commit；`FlowMediaReader` + 短会话 `AgentToolExecutor`） |
| 发布 Flow 跑图 | `miles_portal/.../agent/chat_entry.py`（`_run_published_flow`，`flow_run_context` 后、`run` 前） |
| A2A 宿主 | `miles_portal/.../a2a/invoke.py`（`run_a2a_host_chat`：Peer HTTP / 编排 LLM 前） |
| A2A 规划 LLM | 同上 `plan_a2a_peers`（`resolve_model_for_invoke` 后、`ainvoke_chat` 前；`db is None` 时跳过 commit） |
| 工作台 KB 检索 API | `miles_portal/.../kb/services/kb/search.py`（`search` / `_search_visual`：embed、向量后端、S3/OCR 等慢 IO 前） |
| 生成编排厂商 HTTP | `miles_portal/.../generative/services/orchestration.py`（配额校验后、`generate_*_bytes` 厂商 HTTP 前） |
| 模型健康探测 | `miles_worker/.../model_health.py`（load 会话关闭 / 释放连接后探测，写回另开会话） |

**尚未对齐**（仍可能在长 IO 期间持有同一会话）：

- KB ingest（embedding / 向量写入等分阶段事务；见 `miles_portal/.../kb/services/ingest.py` 与 `miles_ai/rag/pipeline/ingest.py`）
- 生成物落盘（可选）：`generative/services/persist.py` 的 `persist_generated_bytes` 在对象存储 `upload_bytes` 期间仍可能占用同一 DB 会话

更完整的骨架说明见 [backend-reference-framework.md](../architecture/backend-reference-framework.md) 中 `infra/db` 段落。
