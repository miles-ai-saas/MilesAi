# 生成阶段不持有数据库连接（Agent RAG 链路）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让一次 agent chat 请求在生成阶段（LLM / 厂商 API 调用期间）不持有数据库连接：检索与附图解析走短会话，生成前提交请求事务，生成入口的签名不含 `db`。

**Architecture:** 把 RAG 生成链路切成三段——前置（读 + hook，用请求会话）、检索与附图（短会话，用完释放）、生成（无 `db` 句柄）。结构性保证来自签名：生成函数没有 `db` 参数，想碰数据库也碰不到。同时把 `ChatUsageSink` 从调用方会话解耦（对齐既有的 `FlowUsageSink`）。

**Tech Stack:** Python 3.11+ / SQLAlchemy 2 async / pytest / ruff / uv workspace

**设计依据：** [2026-09-14-rag-generation-db-connection-design.md](../specs/2026-09-14-rag-generation-db-connection-design.md)

## Global Constraints

- **实施位置（用户已确认）**：worktree `.worktrees/rag-generation-db-connection`，分支 `feat/rag-generation-db-connection`（基线 `d1289bb3`，基线全绿：ruff clean / import-linter 6 kept / **1022 passed**）。**不得在 `main` 上直接改代码。**
- 所有命令在 worktree 的 `backend/` 目录下执行。
- 本仓库 `uv` 的坑：裸 `uv sync` / `uv run`（不带 `--all-packages`）会**卸载其余成员包**，所有命令一律带 `uv run --all-packages --group dev`。
- Commit message **必须简体中文**，Conventional Commits：`<type>(<scope>): <中文简述>`。用 HEREDOC 传多行 message。
- 每个 Task 结束必须全绿，门禁命令（CI 同款，缺一不可）：
  - `uv run --all-packages --group dev ruff format --check .`
  - `uv run --all-packages --group dev ruff check .`
  - `uv run --all-packages --group dev lint-imports`
  - `uv run --all-packages --group dev python -m pytest -q`
- SDD 工作区 `.superpowers/sdd/` 由 `scripts/sdd-workspace` 初始化，自带内容为 `*` 的 `.gitignore`（自忽略）；任务简报/实现报告/评审包/进度 ledger 都放那里。一次性探针、草稿脚本放 `/tmp`，不要留在 `backend/` 或 `tests/` 里（会被误提交）。
- 分层判据不得破坏：`miles_ai` ✗→ `miles_portal`；`miles_portal` ✗→ `miles_admin`；`miles_core` ✗→ `miles_ai`。
- **不改对外契约**：不改 API 路由、不改响应字段、不改 OpenAPI 快照。
- **不引入新依赖**。
- 不改行为的部分：`answer` / `hits` / `steps` 内容、检索用 `retrieve_query` / prompt 用 `prompt_query` 的区分、用量计量口径。

## 文件结构

| 文件 | 职责 | 本计划中的变化 |
|------|------|----------------|
| `packages/miles-portal/src/miles_portal/tenant/models/services/usage.py` | 模型用量记录（sink） | `ChatUsageSink` 改为自开短会话，删 `db` 参数 |
| `packages/miles-ai/src/miles_ai/rag/generate/answer.py` | 线性 RAG：检索 + 生成 | 抽出 `build_rag_prompt` / `generate_rag_answer`（无 `db`）；删除组合入口 `rag_answer` |
| `packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/rag_qa.py` | RAG 图节点 | `generate` / `fallback` 复用 `generate_rag_answer` |
| `packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py` | L1 编排 | 检索移到 L1（短会话）、生成前 commit、`media_reader` 换短会话实现 |
| `packages/miles-ai/src/miles_ai/rag/generate/__init__.py` | 子包 barrel | 导出调整 |
| `packages/miles-ai/src/miles_ai/integrations/__init__.py`、`integrations/langchain/__init__.py` | 惰性 shim | 导出名同步 |
| `tests/...` | 测试 | 新增 5 个测试文件（Task 1/2/3/4/5），迁移 3 个既有文件（`test_chat_usage_accumulation`、`test_rag_answer_stream`、`test_rag_multimodal`） |

---

### Task 1: 探针——用量累计是否能跨 RAG 图节点回到调用方（只诊断，不提交断言破损行为的测试）

**为什么先做：** 设计 §8.1。`ChatUsageSink` 走 `_chat_usage_acc` ContextVar 累计 token 供 `AgentChatCall` 汇总。若 LangGraph 在独立 task 中跑节点，节点内写入不会回到调用方上下文，`AgentChatCall` 的 token 会恒为 0（而 `ModelUsageLog` 行正常）。这是**改造前就可能存在**的问题。

**用户已裁决（2026-09-14）：** 本 Task **只诊断**——探针脚本放 `/tmp`（一次性脚本不进仓库；SDD 工作区 `.superpowers/sdd/` 只放简报/报告/ledger），跑出真实结论后按结论二选一：
- **丢失** ⇒ 当场按 Step 3A 修复（把累计从「重新绑定元组」改为「原地累加共享对象」）并提交修复 + 正向测试；
- **未丢失** ⇒ 按 Step 3B 提交一条正向测试固化实测行为，并在报告里注明「当前依赖节点内联执行」这一脆弱前提。

任一分支都**不得提交**「断言 totals == (0, 0)」这种把缺陷当基线的测试。

**Files:**
- Probe（不提交，仓库外）: `/tmp/miles-probe-usage-contextvar.py`
- Test: `backend/tests/tenant/agents/test_rag_usage_accumulation.py`（新建，按分支写正向断言）
- Modify（仅 Step 3A 分支）: `backend/packages/miles-portal/src/miles_portal/tenant/models/services/usage.py`
- Modify（仅 Step 3A 分支）: `backend/tests/tenant/models/test_chat_usage_accumulation.py`、`backend/tests/tenant/models/test_flow_usage_sink.py`

**Interfaces:**
- Consumes: `miles_ai.integrations.langgraph.graphs.rag_qa.build_rag_qa_graph`、`miles_portal.tenant.models.services.usage.{begin_chat_usage_accumulation, end_chat_usage_accumulation, get_chat_usage_totals, record_model_usage, UsageRecordContext}`
- Produces: 一条**带证据**的结论 + 一条正向回归测试（Step 3A 还产出 `ChatUsageAccumulator`：`usage.py` 中的可变累计器，`add(*, prompt_tokens, completion_tokens)` / `totals() -> tuple[int, int]`）。

- [ ] **Step 1: 写探针脚本（仓库外，不提交）**

创建 `/tmp/miles-probe-usage-contextvar.py`：

```python
"""探针：RAG 图节点内写入的用量累计，是否回到调用方上下文。

``AgentChatCall`` 的 token 来自 ``_chat_usage_acc`` ContextVar；若 LangGraph 在
独立 task 中执行节点，节点内的写入属于另一个上下文副本，调用方取到的是 0——
而 ``ModelUsageLog`` 行照常写入，症状会表现为「有日志、无汇总」，极难排查。

只打印结论，不做断言：断言会把「当前行为」写成基线，而这里要的是事实。
"""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import miles_ai.integrations.langgraph.graphs.rag_qa as rag_qa
from miles_ai.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph
from miles_portal.tenant.models.services.usage import (
    UsageRecordContext,
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
    record_model_usage,
)


class _FakeDb:
    """record_model_usage 只需要 add() 与 flush()。"""

    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None


class _ShortSession:
    """AsyncSessionLocal 替身：retrieve 节点会开短会话。"""

    async def __aenter__(self) -> "_ShortSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def main() -> None:
    tenant_id = uuid4()
    db = _FakeDb()
    model = AsyncMock()
    model.id = uuid4()
    model.name = "m"

    async def fake_record(*, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        await record_model_usage(
            UsageRecordContext(db=db, tenant_id=tenant_id, model=model, source="chat", source_id=uuid4()),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    sink = AsyncMock()
    sink.record = AsyncMock(side_effect=fake_record)

    async def fake_ainvoke(_model, _messages, **kwargs):
        # 真实 adapter 在 LLM 返回后调 sink.record；必须复刻，否则探针无效
        if kwargs.get("usage_sink") is not None:
            await kwargs["usage_sink"].record(prompt_tokens=7, completion_tokens=3)
        return "答案"

    rag_qa.AsyncSessionLocal = _ShortSession
    rag_qa.retrieve_hits = AsyncMock(return_value=[{"content": "片段", "score": 0.9}])
    rag_qa.ainvoke_chat = AsyncMock(side_effect=fake_ainvoke)

    initial = {
        "query": "问题",
        "prompt_query": "问题",
        "system_prompt": "sys",
        "kb_ids": ["kb1"],
        "tenant_id": str(tenant_id),
        "top_k": 5,
        "temperature": 0.7,
        "max_retries": 1,
        "retry_count": 0,
        "relevance_threshold": 0.35,
        "use_llm_grade": False,
        "media": [],
        "agent_id": str(uuid4()),
        "hits": [],
        "steps": [],
    }
    config = {"configurable": {"model": model, "usage_sink": sink, "kb_retrieval": object()}}

    token = begin_chat_usage_accumulation()
    try:
        await build_rag_qa_graph().compile().ainvoke(initial, config)
        totals = get_chat_usage_totals()
    finally:
        end_chat_usage_accumulation(token)

    print(f"图内 sink 记录行数：{len(db.rows)}")
    print(f"调用方读到的累计：{totals}")
    print("结论：" + ("丢失（需按 Step 3A 修复）" if totals == (0, 0) else "未丢失（按 Step 3B 固化）"))


asyncio.run(main())
```

> `rag_qa.AsyncSessionLocal` / `retrieve_hits` / `ainvoke_chat` 用**属性赋值**而非 `monkeypatch`：探针是独立脚本，没有 pytest fixture。

- [ ] **Step 2: 跑探针，记录真实结论**

Run: `uv run --all-packages --group dev python /tmp/miles-probe-usage-contextvar.py`

Expected 输出形如：

```text
图内 sink 记录行数：1
调用方读到的累计：(0, 0)   ← 或 (7, 3)
结论：丢失（需按 Step 3A 修复）  ← 或 未丢失（按 Step 3B 固化）
```

把**原始输出**抄进报告。`图内 sink 记录行数` 必须 ≥ 1，否则是探针没接上（`sink.record` 未被调用），结论无效——此时先修探针再重跑。

⚠️ 若 Python 路径下 `build_rag_qa_graph().compile()` 因缺 checkpointer 报错，改用 `from miles_ai.integrations.langgraph.checkpointer import get_compiled_rag_graph` 并调用 `get_compiled_rag_graph()`（它内部回退 `MemorySaver`）；把这一步的调整如实写进报告。

- [ ] **Step 3A: 若结论为「丢失」——改为原地累加共享对象**

**为什么这样修（不要改成「显式对象穿透」的重构）：** 根因是 `record_model_usage` 用 `ContextVar.set()` **重新绑定**元组，子 context 的绑定不回流父 context。把累计器换成**可变对象**、只 `set()` 一次（在 `begin`，父 context 里）之后一律**原地累加**，则子 context 与父 context 拿到的是同一个实例，写入天然可见。这既修掉跨 task 丢失，又不新增任何参数穿透、不改任何调用方签名。

改 `usage.py`：

```python
@dataclass
class ChatUsageAccumulator:
    """单轮 chat 的 token 累计器。

    刻意做成**可变对象**：``_chat_usage_acc`` 里存的是它的引用，记录用量时原地累加。
    若沿用「存元组 + 每次 set() 新元组」，绑定只会写进当前 context——LangGraph 在
    子 task 里执行节点时，父 context 读到的仍是初始值，``AgentChatCall`` 会恒记 0 token。
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    def add(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)

    def totals(self) -> tuple[int, int]:
        return self.prompt_tokens, self.completion_tokens


_chat_usage_acc: ContextVar[ChatUsageAccumulator | None] = ContextVar("_chat_usage_acc", default=None)


def begin_chat_usage_accumulation() -> Token[ChatUsageAccumulator | None]:
    """单轮 Agent chat 开始时重置 Token 累计（供调用记录写入）。"""
    return _chat_usage_acc.set(ChatUsageAccumulator())


def end_chat_usage_accumulation(token: Token[ChatUsageAccumulator | None]) -> None:
    """恢复到本轮 chat 累计前的上下文状态。"""
    _chat_usage_acc.reset(token)


def get_chat_usage_totals() -> tuple[int, int]:
    """返回当前轮次累计的 (prompt_tokens, completion_tokens)。"""
    acc = _chat_usage_acc.get()
    if acc is None:
        return (0, 0)
    return acc.totals()
```

并把 `record_model_usage` 里的累加段：

```python
    if ctx.source == "chat" and ctx.source_id is not None:
        acc = _chat_usage_acc.get()
        if acc is not None:
            p, c = acc
            _chat_usage_acc.set((p + max(0, prompt_tokens), c + max(0, completion_tokens)))
```

改为：

```python
    if ctx.source == "chat" and ctx.source_id is not None:
        acc = _chat_usage_acc.get()
        if acc is not None:
            # 原地累加，不重新绑定：子 task 里的写入必须能被父 context 看见
            acc.add(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
```

- [ ] **Step 3A-2: 迁移直接操作私有变量的既有测试**

`tests/tenant/models/test_chat_usage_accumulation.py` 的 `test_chat_usage_accumulation` 当前直接 `usage_mod._chat_usage_acc.set((120, 30))`，元组形态已不存在，改为：

```python
def test_chat_usage_accumulation():
    token = begin_chat_usage_accumulation()
    try:
        acc = usage_mod._chat_usage_acc.get()
        assert acc is not None
        acc.add(prompt_tokens=120, completion_tokens=30)
        assert get_chat_usage_totals() == (120, 30)
    finally:
        end_chat_usage_accumulation(token)
    assert get_chat_usage_totals() == (0, 0)
```

（`tests/tenant/models/test_flow_usage_sink.py:104` 断言 `get_chat_usage_totals() == (0, 0)`——`FlowUsageSink` 的 `source="flow"` 本就不参与 chat 累计，该断言不受影响，**不改**。）

- [ ] **Step 3B: 若结论为「未丢失」——固化实测行为**

跳过 Step 3A/3A-2，直接进 Step 4，测试断言**实测到的真实值**（例：`assert totals == (7, 3)`），并在 docstring 写明：

```python
"""回归：RAG 图节点内写入的用量累计必须回到调用方上下文。

实测（2026-09-14 探针）：节点内 sink.record 的 token 能回到调用方——当前 LangGraph
是内联 await 执行节点，未另开 task。本测试锁住该行为：一旦将来改为在独立 task 中
执行节点，累计会静默丢失（AgentChatCall 恒记 0 token，而 ModelUsageLog 行照常），
本测试即会失败。
"""
```

同时把「当前依赖节点内联执行」这一脆弱前提写进报告与 Task 8 的 spec 修订记录。

- [ ] **Step 4: 写正向回归测试（两个分支都要）**

创建 `backend/tests/tenant/agents/test_rag_usage_accumulation.py`：内容与 Step 1 的探针脚本相同，但改成 pytest 形态——`monkeypatch.setattr(rag_qa, ...)` 替代属性赋值、把 `main()` 体搬进 `async def test_graph_node_usage_reaches_caller_contextvar(monkeypatch)`、末尾断言改为：

```python
    # 探针有效性：图内 sink 必须真的记录过，否则本测试不能证明任何事情
    assert db.rows, "sink.record 未被调用，测试无效"
    assert totals == (7, 3), (
        "图节点内写入的 chat 用量必须回到调用方；若为 (0, 0)，说明累计又退回"
        "「重新绑定 ContextVar」的写法（见 usage.py 的 ChatUsageAccumulator 说明）。"
    )
```

> Step 3A 分支：该断言在修复后为真（修复前为假），这正是修复的回归护栏。
> Step 3B 分支：把 `(7, 3)` 换成实测值。

- [ ] **Step 5: 门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 6: 变异测试（仅 Step 3A 分支，证明护栏有效）**

把 `record_model_usage` 的原地累加临时改回 `_chat_usage_acc.set((p + ..., c + ...))`（先 `acc.totals()` 取值），重跑：

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_rag_usage_accumulation.py -q`

Expected（变异态）：FAIL（`(0, 0) != (7, 3)`）。还原后 PASS。

- [ ] **Step 7: Commit**

Step 3A 分支：

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/models/services/usage.py \
        backend/tests/tenant/models/test_chat_usage_accumulation.py \
        backend/tests/tenant/agents/test_rag_usage_accumulation.py
git commit -F - <<'EOF'
fix(usage): chat 用量累计改为原地累加，修复跨 task 丢失

累计原先存元组、每次记录都 ContextVar.set() 新元组，绑定只写进当前 context。
LangGraph 在子 task 执行节点时，父 context 读到的仍是 begin 时的 (0, 0)，于是
AgentChatCall 的 prompt/completion token 恒为 0，而 ModelUsageLog 行照常写入——
「有日志、无汇总」，事后极难定位。

改为存入可变累加器（ChatUsageAccumulator）并在记录时原地累加：父子 context 拿到
同一实例，写入由此可见；begin 仍只 set() 一次，避免任何子 context 重绑定。
EOF
```

Step 3B 分支：

```bash
git add backend/tests/tenant/agents/test_rag_usage_accumulation.py
git commit -F - <<'EOF'
test(usage): 钉住 RAG 图节点的用量累计能回到调用方

AgentChatCall 的 token 来自 _chat_usage_acc ContextVar，而 ModelUsageLog 行由会话
写入。实测当前 LangGraph 内联 await 执行节点，累计能正常回到调用方——但该结论
依赖「不另开 task」这一前提，一旦改动就会静默退化为恒记 0 token。

用真实编译图（仅替换会话工厂、检索与 LLM）把行为固定下来。
EOF
```

---

### Task 2: `ChatUsageSink` 与会话解耦（自开短会话）

**为什么：** `ChatUsageSink` 用调用方会话，`record` 在每次 LLM 调用之后重新抓住请求会话，使「生成期间不占连接」无法达成。改为对齐 `FlowUsageSink`（自开短会话、即写即提交）。

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/models/services/usage.py`（`ChatUsageSink`，约 78-107 行）
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py:416`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/compliance/services/compliance/media_audit.py:77`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/invoke.py:151`
- Modify: `backend/tests/tenant/models/test_chat_usage_accumulation.py`
- Test: `backend/tests/tenant/models/test_chat_usage_sink_session.py`（新建）

**Interfaces:**
- Consumes: `AsyncSessionLocal`（`miles_core.infra.db`）、`UsageRecordContext` / `record_model_usage`（同文件）
- Produces: `ChatUsageSink(*, tenant_id: UUID, model: ModelConfig, source_id: UUID | None = None)` —— **无 `db` 参数**；`record(*, prompt_tokens: int = 0, completion_tokens: int = 0) -> None` 自开短会话并 commit。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/tenant/models/test_chat_usage_sink_session.py`：

```python
"""ChatUsageSink 不得借用调用方会话。

生成阶段要释放请求会话连接，前提是用量写入不再挂在调用方事务上。这里锁定两点：
构造签名不含 db；record 自开短会话并提交，且完全不触碰调用方会话。
"""

import inspect
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import ChatUsageSink


def _model() -> ModelConfig:
    return ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")


class _ShortSession:
    """替身：记录 add 的行，并记录是否 commit。"""

    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def test_chat_usage_sink_has_no_db_parameter():
    """结构不变量：不接收调用方会话，就不可能在生成期间抓住它。"""
    assert "db" not in inspect.signature(ChatUsageSink.__init__).parameters


@pytest.mark.asyncio
async def test_record_uses_its_own_session_and_commits(monkeypatch):
    short = _ShortSession()
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", lambda: _cm(short))

    class _Caller:
        """调用方会话替身：被碰一下就记账。"""

        def __init__(self) -> None:
            self.touched = 0

        def add(self, row: object) -> None:
            self.touched += 1

        async def flush(self) -> None:
            self.touched += 1

    caller = _Caller()
    model = _model()
    source_id = uuid4()

    sink = ChatUsageSink(tenant_id=uuid4(), model=model, source_id=source_id)
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert len(short.rows) == 1
    row = short.rows[0]
    assert isinstance(row, ModelUsageLog)
    assert row.model_config_id == model.id
    assert row.source == "chat"
    assert row.source_id == source_id
    assert short.commits == 1
    assert caller.touched == 0, "不得触碰调用方会话"


class _cm:
    """最小 async context manager（AsyncSessionLocal 的替身）。"""

    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/models/test_chat_usage_sink_session.py -v`

Expected: FAIL —— `test_chat_usage_sink_has_no_db_parameter` 报 `'db' in parameters`；`test_record_uses_its_own_session_and_commits` 报 `TypeError: ChatUsageSink.__init__() got an unexpected keyword argument`。

- [ ] **Step 3: 改 `ChatUsageSink`**

把 `usage.py` 的 `ChatUsageSink` 改为（保留类 docstring 的分工说明）：

```python
class ChatUsageSink:
    """对话链路的用量记录器：会话 token 累计 + 落 ModelUsageLog。

    实现 L3 ``UsageSink`` 协议，由 L1 装配（如 AgentService、flow 运行入口）
    构造并注入引擎；``source_id`` 为对话 agent_id，用于 chat 用量累计。

    ``record`` 自开短会话并提交，**不借用调用方会话**：生成阶段的 LLM 调用之间
    会记录用量，若挂在请求事务上就等于整段生成期间占住一个连接。token 仍累加到
    ``_chat_usage_acc`` ContextVar（与 Session 无关），供 ``AgentChatCall`` 汇总。
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        model: ModelConfig,
        source_id: UUID | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._model = model
        self._source_id = source_id

    async def record(self, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """实现 ``UsageSink`` 协议：自开短会话写 chat 来源用量并提交。"""
        if max(0, prompt_tokens) + max(0, completion_tokens) <= 0:
            return
        async with AsyncSessionLocal() as db:
            await record_model_usage(
                UsageRecordContext(
                    db=db,
                    tenant_id=self._tenant_id,
                    model=self._model,
                    source="chat",
                    source_id=self._source_id,
                ),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            await db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/models/test_chat_usage_sink_session.py -v`

Expected: PASS。

- [ ] **Step 5: 更新 3 处构造点（删 `db=`）**

`chat_rag.py:416` 附近：

```python
        return ChatUsageSink(
            tenant_id=self.ctx.tenant_id,
            model=model,
            source_id=source_id,
        )
```

`media_audit.py:77`：

```python
        usage_sink = ChatUsageSink(tenant_id=ctx.tenant_id, model=model)
```

`a2a/invoke.py:151`：

```python
    usage_sink = ChatUsageSink(
        tenant_id=tenant_id,
        model=model,
        source_id=parent.id,
    )
```

- [ ] **Step 6: 迁移既有测试**

`tests/tenant/models/test_chat_usage_accumulation.py` 的 `test_chat_usage_sink_accumulates_and_flushes` 改为不传 `db`、改为断言短会话（`usage_mod.AsyncSessionLocal` 替身）内写入的行：

```python
@pytest.mark.asyncio
async def test_chat_usage_sink_accumulates_and_commits(monkeypatch):
    short = _ShortSession()
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", lambda: _cm(short))

    begin_chat_usage_accumulation()
    model_id = uuid4()
    source_id = uuid4()
    sink = ChatUsageSink(
        tenant_id=uuid4(),
        model=ModelConfig(id=model_id, name="m", provider="openai", model_name="x"),
        source_id=source_id,
    )
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert get_chat_usage_totals() == (100, 20)
    row = short.rows[0]
    assert isinstance(row, ModelUsageLog)
    assert row.model_config_id == model_id
    assert row.source == "chat"
    assert row.source_id == source_id
    assert row.prompt_tokens == 100
    assert row.completion_tokens == 20
    assert short.commits == 1
```

在同文件顶部复用 Task 2 Step 1 里的 `_ShortSession` 与 `_cm`（**复制**这两个小类到本文件，不要跨测试文件 import，保持测试文件自持）：

```python
class _ShortSession:
    """替身：记录 add 的行并记录 commit。"""

    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class _cm:
    """最小 async context manager（AsyncSessionLocal 的替身）。"""

    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False
```

同时删掉不再使用的 `db_session` fixture（若 `ruff` 报未使用）。

- [ ] **Step 7: 跑相关测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/tenant/models tests/tenant/compliance tests/tenant/a2a -q && \
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 8: 变异测试（确认护栏有效）**

临时把 `ChatUsageSink.__init__` 加回 `db: AsyncSession` 参数并让 `record` 改回用 `self._db`，重跑 Step 1 的测试，确认**失败**；然后还原。

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/models/test_chat_usage_sink_session.py -q`

Expected（变异态）：FAIL。还原后 PASS。

- [ ] **Step 9: Commit**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/models/services/usage.py \
        backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py \
        backend/packages/miles-portal/src/miles_portal/tenant/compliance/services/compliance/media_audit.py \
        backend/packages/miles-portal/src/miles_portal/tenant/a2a/invoke.py \
        backend/tests/tenant/models/test_chat_usage_sink_session.py \
        backend/tests/tenant/models/test_chat_usage_accumulation.py
git commit -F - <<'EOF'
refactor(usage): ChatUsageSink 改为自开短会话，不再挂调用方事务

用量在每次 LLM 调用之后写入，挂在请求会话上就等于整段生成期间占住一个连接，
与 flow 路径的 FlowUsageSink 策略相反，同一文件里两套语义也难解释。

改为自开会话即写即提交：token 已被真实消耗，现状下若生成后续失败会被回滚而少计。
token 累计仍走 ContextVar，与 Session 无关，AgentChatCall 汇总口径不变。
EOF
```

---

### Task 3: 抽出无 `db` 的生成入口 `generate_rag_answer` 与 `build_rag_prompt`

**为什么：** 生成阶段的「prompt 构造 + 附图解析 + `ainvoke_chat`」在 `answer.rag_answer` 与 `rag_qa.generate` 里逐字重复，且都接收 `db`。抽成不含 `db` 的生成入口，既去重又把「生成期间不碰 DB」变成签名级不变量。**本 Task 保留 `rag_answer` 组合入口**（改成调用新函数），保证全程绿灯；删除放到 Task 6。

**Files:**
- Modify: `backend/packages/miles-ai/src/miles_ai/rag/generate/answer.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/rag/generate/__init__.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/__init__.py`
- Test: `backend/tests/rag/test_generate_rag_answer.py`（新建）

**Interfaces:**
- Consumes: `build_rag_user_prompt`（同包 `context.py`）、`build_invoke_messages_with_media`（`miles_ai.integrations.chat.multimodal`）、`ainvoke_chat`、`MediaRefIn`、`MediaReader`、`OnDelta`、`UsageSink`、`ModelConfig`
- Produces（后续 Task 依赖的精确签名）：
  - `def build_rag_prompt(*, system_prompt: str, query: str, hits: list[dict[str, Any]]) -> str`
  - `async def generate_rag_answer(*, model: ModelConfig, prompt: str, media: list[MediaRefIn] | None = None, media_reader: MediaReader | None = None, temperature: float = 0.7, on_delta: OnDelta | None = None, usage_sink: UsageSink | None = None) -> str`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/rag/test_generate_rag_answer.py`：

```python
"""无 db 的生成入口：签名不变量 + prompt 构造 + 附图错误语义。

生成阶段要释放连接，靠的是「生成函数拿不到 db」这个签名级约束；本文件把
签名钉住，并覆盖 prompt 构造的两种分支与缺 media_reader 的显式报错。
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.rag.generate.answer import build_rag_prompt, generate_rag_answer
from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn


def test_generate_rag_answer_signature_has_no_db():
    params = inspect.signature(generate_rag_answer).parameters
    assert "db" not in params
    assert "kb_ids" not in params
    assert "tenant_id" not in params
    assert "bindings" not in params


def test_build_rag_prompt_without_hits_uses_system_and_question():
    prompt = build_rag_prompt(system_prompt="你是助手", query="问题", hits=[])
    assert prompt == "你是助手\n\n用户问题：问题"


def test_build_rag_prompt_with_hits_includes_context():
    prompt = build_rag_prompt(
        system_prompt="你是助手",
        query="问题",
        hits=[{"content": "片段", "score": 0.9}],
    )
    assert "你是助手" in prompt
    assert "片段" in prompt
    assert prompt.endswith("问题")


@pytest.mark.asyncio
async def test_generate_rag_answer_passes_prompt_and_forwards_on_delta():
    async def delta(_: str) -> None:
        pass

    usage_sink = object()
    with patch(
        "miles_ai.rag.generate.answer.ainvoke_chat",
        new_callable=AsyncMock,
        return_value="答",
    ) as mock_chat:
        answer = await generate_rag_answer(
            model=MagicMock(),
            prompt="拼好的 prompt",
            temperature=0.3,
            on_delta=delta,
            usage_sink=usage_sink,
        )

    assert answer == "答"
    assert mock_chat.await_args.args[1] == [{"role": "user", "content": "拼好的 prompt"}]
    assert mock_chat.await_args.kwargs["temperature"] == 0.3
    assert mock_chat.await_args.kwargs["on_delta"] is delta
    assert mock_chat.await_args.kwargs["usage_sink"] is usage_sink


@pytest.mark.asyncio
async def test_generate_rag_answer_with_media_without_reader_raises():
    with pytest.raises(BadRequestError, match="media_reader"):
        await generate_rag_answer(
            model=MagicMock(),
            prompt="p",
            media=[MediaRefIn(attachment_id=uuid4())],
        )


@pytest.mark.asyncio
async def test_generate_rag_answer_resolves_media_before_llm():
    reader = MagicMock()
    with (
        patch(
            "miles_ai.rag.generate.answer.build_invoke_messages_with_media",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        ) as mock_build,
        patch(
            "miles_ai.rag.generate.answer.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答",
        ),
    ):
        await generate_rag_answer(
            model=MagicMock(),
            prompt="p",
            media=[MediaRefIn(attachment_id=uuid4())],
            media_reader=reader,
        )

    assert mock_build.await_args.args[0] is reader
    assert mock_build.await_args.kwargs["prompt_text"] == "p"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --all-packages --group dev python -m pytest tests/rag/test_generate_rag_answer.py -v`

Expected: FAIL —— `ImportError: cannot import name 'build_rag_prompt'`。

- [ ] **Step 3: 实现两个函数**

在 `answer.py` 中，`rag_answer` 之前插入：

```python
def build_rag_prompt(*, system_prompt: str, query: str, hits: list[dict[str, Any]]) -> str:
    """按是否有命中拼接生成用 prompt（无命中时不带参考片段）。"""
    if not hits:
        return f"{system_prompt}\n\n用户问题：{query}"
    return build_rag_user_prompt(system_prompt=system_prompt, query=query, hits=hits)


async def generate_rag_answer(
    *,
    model: ModelConfig,
    prompt: str,
    media: list[MediaRefIn] | None = None,
    media_reader: MediaReader | None = None,
    temperature: float = 0.7,
    on_delta: OnDelta | None = None,
    usage_sink: UsageSink | None = None,
) -> str:
    """生成阶段：附图解析 + ``ainvoke_chat``。**不接收 db**。

    检索已由调用方（L1）在短会话内完成，hits 拼进 ``prompt``；本函数因此可以
    在「连接已归还池」的状态下运行——这是「生成期间不持有连接」的结构性保证，
    签名里没有 db 是刻意的，请勿为了方便再加回来。
    """
    messages: list[dict[str, Any]]
    if media:
        if media_reader is None:
            raise BadRequestError("媒体读取器未装配（media_reader），无法解析附图")
        messages = await build_invoke_messages_with_media(
            media_reader,
            prompt_text=prompt,
            media=media,
        )
    else:
        messages = [{"role": "user", "content": prompt}]
    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        usage_sink=usage_sink,
        on_delta=on_delta,
    )
```

- [ ] **Step 4: 把 `rag_answer` 改为组合调用（行为不变）**

把 `rag_answer` 体（从 `search_q = ...` 到 `return answer, hits`）替换为：

```python
    search_q = (retrieve_query if retrieve_query is not None else query).strip()
    hits = await retrieve_hits(
        search_q,
        tenant_id=tenant_id,
        kb_ids=kb_ids,
        db=db,
        top_k=top_k,
        bindings=bindings,
    )
    prompt = build_rag_prompt(system_prompt=system_prompt, query=query, hits=hits)
    answer = await generate_rag_answer(
        model=model,
        prompt=prompt,
        media=media,
        media_reader=media_reader,
        temperature=temperature,
        on_delta=on_delta,
        usage_sink=usage_sink,
    )
    return answer, hits
```

- [ ] **Step 5: 跑测试确认通过**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/rag -v
```
Expected: PASS（新文件 + `test_rag_answer_stream.py` / `test_rag_multimodal.py` 均通过——后者仍 patch `miles_ai.rag.generate.answer.ainvoke_chat`，路径未变）。

- [ ] **Step 6: 更新 barrel 与惰性 shim**

`rag/generate/__init__.py` 改为：

```python
"""
RAG 生成子包（L2，线性路径）。

导出
----
- ``retrieve_hits``：多 KB 检索（画布、LangGraph retrieve 节点）
- ``build_rag_prompt`` / ``generate_rag_answer``：拼 prompt + 生成（生成阶段无 db）
- ``rag_answer``：检索 + 生成一站式（兼容保留，Task 6 删除）
- ``format_hits_context`` / ``build_rag_user_prompt``：拼 LLM 输入

Agent 默认多轮 RAG 图见 ``integrations.langgraph.graphs.rag_qa``，非本包。
"""

from miles_ai.rag.generate.answer import (
    build_rag_prompt,
    generate_rag_answer,
    rag_answer,
    retrieve_hits,
)
from miles_ai.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_prompt",
    "build_rag_user_prompt",
    "format_hits_context",
    "generate_rag_answer",
    "rag_answer",
    "retrieve_hits",
]
```

`integrations/langchain/__init__.py`：在 `__all__` 加入 `"build_rag_prompt"`、`"generate_rag_answer"`（保持字母序），并把 `__getattr__` 的元组改为：

```python
    if name in (
        "retrieve_hits",
        "format_hits_context",
        "build_rag_user_prompt",
        "build_rag_prompt",
        "generate_rag_answer",
        "rag_answer",
    ):
        from miles_ai.rag import generate as rag_gen

        return getattr(rag_gen, name)
```

`integrations/__init__.py`：在 `__all__` 加入 `"build_rag_prompt"`、`"generate_rag_answer"`（字母序），并把转发元组改为：

```python
    if name in (
        "ainvoke_chat",
        "split_text",
        "rag_answer",
        "retrieve_hits",
        "build_rag_prompt",
        "generate_rag_answer",
    ):
        from miles_ai.integrations import langchain as lc

        return getattr(lc, name)
```

- [ ] **Step 7: 门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 8: Commit**

```bash
git add backend/packages/miles-ai/src/miles_ai/rag/generate/answer.py \
        backend/packages/miles-ai/src/miles_ai/rag/generate/__init__.py \
        backend/packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py \
        backend/packages/miles-ai/src/miles_ai/integrations/__init__.py \
        backend/tests/rag/test_generate_rag_answer.py
git commit -F - <<'EOF'
refactor(rag): 抽出无 db 的生成入口 generate_rag_answer

「拼 prompt + 解析附图 + ainvoke_chat」这段在 rag_answer 与 rag_qa 节点里逐字
重复，且都接收 db，导致生成阶段必然持有连接。

抽成 build_rag_prompt 与 generate_rag_answer：前者收敛无命中兜底话术，后者
签名不含 db——「生成期间不碰库」由签名而非注释保证。rag_answer 暂留为组合入口，
调用方迁移完再删。
EOF
```

---

### Task 4: `rag_qa` 的 `generate` / `fallback` 节点复用生成入口

**为什么：** 消除与 `answer.py` 逐字重复的 prompt 构造与附图处理。

**Files:**
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/rag_qa.py`
- Modify: `backend/tests/rag/test_rag_multimodal.py`（patch 目标重定向）
- Modify: `backend/tests/rag/test_rag_answer_stream.py`（patch 目标重定向）
- Modify: `backend/tests/tenant/agents/test_rag_usage_accumulation.py`（patch 目标重定向，见 Step 5）
- Test: `backend/tests/rag/test_rag_qa_nodes_share_generate.py`（新建）

**Interfaces:**
- Consumes: `build_rag_prompt` / `generate_rag_answer`（Task 3）
- Produces: `generate` / `fallback` 节点保持**相同返回结构**（`answer` + `steps`，字段与顺序不变）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/rag/test_rag_qa_nodes_share_generate.py`：

```python
"""rag_qa 的 generate / fallback 必须复用无 db 的生成入口。

两节点原先各自复制了一份「拼 prompt + 解析附图 + ainvoke_chat」，既要维护两处，
又都绕过生成入口的签名约束。这里证明两者都走 generate_rag_answer。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.integrations.langgraph.graphs.rag_qa import fallback, generate


def _state(*, hits: list | None = None) -> dict:
    return {
        "tenant_id": str(uuid4()),
        "system_prompt": "你是助手",
        "query": "检索词",
        "prompt_query": "生成问题",
        "hits": hits if hits is not None else [{"content": "片段", "score": 0.9}],
        "temperature": 0.7,
    }


@pytest.mark.asyncio
async def test_generate_node_uses_generate_rag_answer():
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="答案",
    ) as mock_gen:
        out = await generate(_state(), config)

    assert out["answer"] == "答案"
    mock_gen.assert_awaited_once()
    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "片段" in prompt
    assert mock_gen.await_args.kwargs["media"] is None


@pytest.mark.asyncio
async def test_fallback_node_uses_generate_rag_answer():
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="兜底",
    ) as mock_gen:
        out = await fallback(_state(hits=[]), config)

    assert out["answer"] == "兜底"
    mock_gen.assert_awaited_once()
    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "未检索到" in prompt


@pytest.mark.asyncio
async def test_generate_node_passes_hits_prompt_for_low_relevance_fallback():
    """fallback 有命中时用「相关性较低」话术（与 generate 的正常 prompt 区分）。"""
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="兜底",
    ) as mock_gen:
        await fallback(_state(), config)

    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "相关性较低" in prompt
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --all-packages --group dev python -m pytest tests/rag/test_rag_qa_nodes_share_generate.py -v`

Expected: FAIL —— `AttributeError: <module 'rag_qa'> does not have the attribute 'generate_rag_answer'`。

- [ ] **Step 3: 改节点**

在 `rag_qa.py` 的 import 段加入（与既有 `miles_ai.rag.generate` 同源的 from-import）：

```python
from miles_ai.rag.generate import build_rag_prompt, generate_rag_answer
```

把 `generate` 节点体（`model = _cfg_model(config)` 之后到 `return {...}` 之前）替换为：

```python
    model = _cfg_model(config)
    hits = state.get("hits") or []
    user_q = _prompt_user_query(state)
    prompt = build_rag_prompt(system_prompt=state["system_prompt"], query=user_q, hits=hits)
    media_refs = media_refs_from_items(state.get("media"))
    answer = await generate_rag_answer(
        model=model,
        prompt=prompt,
        media=media_refs,
        media_reader=_cfg_media_reader(config),
        temperature=float(state.get("temperature", 0.7)),
        on_delta=_cfg_on_delta(config),
        usage_sink=_cfg_usage_sink(config),
    )
    return {
        "answer": answer,
        "steps": [
            {
                "type": "generate",
                "node": "generate",
                "hit_count": len(hits),
                "answer_preview": answer[:300],
            }
        ],
    }
```

把 `fallback` 节点体替换为：

```python
    model = _cfg_model(config)
    hits = state.get("hits") or []
    if hits:
        context = format_hits_context(hits)
        prompt = (
            f"{state['system_prompt']}\n\n检索到的内容相关性较低，请谨慎回答并说明依据有限。\n\n参考片段：\n{context}\n\n用户问题：{_prompt_user_query(state)}"
        )
    else:
        prompt = (
            f"{state['system_prompt']}\n\n"
            f"知识库中未检索到与问题直接相关的内容。请基于通用知识简要回答，"
            f"并明确说明未命中企业知识库。\n\n用户问题：{_prompt_user_query(state)}"
        )
    media_refs = media_refs_from_items(state.get("media"))
    answer = await generate_rag_answer(
        model=model,
        prompt=prompt,
        media=media_refs,
        media_reader=_cfg_media_reader(config),
        temperature=float(state.get("temperature", 0.7)),
        on_delta=_cfg_on_delta(config),
        usage_sink=_cfg_usage_sink(config),
    )
    return {
        "answer": answer,
        "steps": [
            {
                "type": "fallback",
                "node": "fallback",
                "hit_count": len(hits),
                "relevance": state.get("relevance"),
            }
        ],
    }
```

在 `_cfg_model` 之后新增三个小取值函数（把「从 configurable 取可选注入」收敛到一处，避免每处重复 `config.get("configurable", {}).get(...)`）：

```python
def _cfg_on_delta(config: RunnableConfig | None) -> Any:
    """从 RunnableConfig.configurable 取 on_delta（可为 None）。"""
    return (config.get("configurable") or {}).get("on_delta") if config else None


def _cfg_usage_sink(config: RunnableConfig | None) -> Any:
    """从 RunnableConfig.configurable 取 usage_sink（可为 None）。"""
    return (config.get("configurable") or {}).get("usage_sink") if config else None


def _cfg_media_reader(config: RunnableConfig | None) -> Any:
    """从 RunnableConfig.configurable 取 media_reader（可为 None）。"""
    return (config.get("configurable") or {}).get("media_reader") if config else None
```

删除 `rag_qa.py` 中不再使用的 import：`build_invoke_messages_with_media`、`ainvoke_chat`、`BadRequestError`（若 `ruff` 报未使用；`media_refs_from_items` 与 `format_hits_context` 仍在使用，保留）。

- [ ] **Step 4: 跑新测试确认通过**

Run: `uv run --all-packages --group dev python -m pytest tests/rag/test_rag_qa_nodes_share_generate.py -v`

Expected: PASS。

- [ ] **Step 5: 重定向既有测试的 patch 目标**

节点内部的 LLM 调用现在发生在 `answer` 模块，`patch("miles_ai.integrations.langgraph.graphs.rag_qa.ainvoke_chat")` 不再能拦截，必须改成 `patch("miles_ai.rag.generate.answer.ainvoke_chat")`。

`tests/rag/test_rag_multimodal.py` 的 `test_generate_node_with_media` 中：

```python
    with (
        patch(
            "miles_ai.rag.generate.answer.build_invoke_messages_with_media",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        ) as mock_build,
        patch(
            "miles_ai.rag.generate.answer.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答案",
        ),
    ):
        out = await generate(state, config)
```

`tests/rag/test_rag_answer_stream.py` 的 `test_generate_node_forwards_on_delta` 与 `test_fallback_node_forwards_on_delta`：把 `patch("miles_ai.integrations.langgraph.graphs.rag_qa.ainvoke_chat", ...)` 改成 `patch("miles_ai.rag.generate.answer.ainvoke_chat", ...)`。

`tests/tenant/agents/test_rag_usage_accumulation.py`（Task 1）：节点不再调用 `rag_qa.ainvoke_chat`（该名字已从模块移除，`monkeypatch.setattr` 会因属性不存在直接报错）。把 import 段加入

```python
import miles_ai.rag.generate.answer as answer_mod
```

并把

```python
    monkeypatch.setattr(rag_qa, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))
```

改成

```python
    monkeypatch.setattr(answer_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))
```

（`rag_qa.retrieve_hits` 与 `rag_qa.AsyncSessionLocal` 仍由 retrieve 节点使用，patch 保持不变。）

- [ ] **Step 6: 跑 RAG 相关测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/rag -q && \
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 7: 变异测试（确认去重真的生效）**

临时把 `generate` 节点改回自己拼 prompt + 调 `ainvoke_chat`（不调 `generate_rag_answer`），重跑 Step 4 的测试，确认**失败**；然后还原。

Run: `uv run --all-packages --group dev python -m pytest tests/rag/test_rag_qa_nodes_share_generate.py -q`

Expected（变异态）：FAIL。还原后 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/rag_qa.py \
        backend/tests/rag/test_rag_qa_nodes_share_generate.py \
        backend/tests/rag/test_rag_multimodal.py \
        backend/tests/rag/test_rag_answer_stream.py \
        backend/tests/tenant/agents/test_rag_usage_accumulation.py
git commit -F - <<'EOF'
refactor(rag): 图节点复用无 db 的生成入口

generate 与 fallback 各自复制了一份「拼 prompt + 解析附图 + ainvoke_chat」，
与 rag_answer 三处重复，且都绕过生成入口的签名约束。

改为复用 build_rag_prompt / generate_rag_answer，并把从 configurable 取
on_delta / usage_sink / media_reader 收敛到三个小函数。节点返回结构与字段不变；
既有测试的 patch 目标随之从节点模块改到 answer 模块。
EOF
```

---

### Task 5: L1 编排——检索走短会话、生成前释放连接、附图读取换短会话

**为什么：** 干线改动。线性路径的检索原先在 `rag_answer` 内部用请求会话，使「调用前提交」失效；现在检索移到 L1 并在短会话内完成，随后提交请求事务，再以无 `db` 的入口生成。LangGraph 路径只需在调用前提交 + 换 `media_reader`。

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py`
- Test: `backend/tests/tenant/agents/test_chat_rag_connection_release.py`（新建）

**Interfaces:**
- Consumes: `build_rag_prompt` / `generate_rag_answer` / `retrieve_hits`（Task 3）、`build_flow_media_reader`（`miles_portal.tenant.attachments.services.media_reader`）、`AsyncSessionLocal`（`miles_core.infra.db`）
- Produces: `rag_chat` 行为不变（`answer` / `sources` / `steps` 内容一致），但在进入生成前 `commit` 请求会话；两条路径的 `media_reader` 均为 `FlowMediaReader`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/tenant/agents/test_chat_rag_connection_release.py`：

```python
"""RAG 生成阶段释放请求会话连接（编排级）。

靠三件事达成：检索与附图解析走短会话、生成前 commit 请求会话、生成入口不含 db。
本文件从 L1 视角断言前两件（第三件见 tests/rag/test_generate_rag_answer.py）。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import chat_rag as chat_rag_mod
from miles_portal.tenant.agents.services.agent.chat_rag import AgentChatRagMixin
from miles_portal.tenant.attachments.services.media_reader import FlowMediaReader


class _TxnDb:
    """记录收尾动作与生成调用次序的最小事务替身。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class _ShortSession:
    """AsyncSessionLocal 替身：记录被开过几次。"""

    def __init__(self) -> None:
        self.entered = 0

    async def __aenter__(self) -> "_ShortSession":
        self.entered += 1
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _run(coro):
    return asyncio.run(coro)


def _svc(db, *, media_query: str = "问题") -> SimpleNamespace:
    async def resolve_system_prompt(agent):
        return "sys"

    async def resolve_invoke_model(cfg):
        return MagicMock()

    async def resolve_chat_media_parts(agent, body):
        return media_query, []

    return SimpleNamespace(
        db=db,
        ctx=SimpleNamespace(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions=frozenset(["agent:chat"]),
            is_superuser=False,
        ),
        resolve_system_prompt=resolve_system_prompt,
        resolve_invoke_model=resolve_invoke_model,
        resolve_chat_media_parts=resolve_chat_media_parts,
        chat_usage_sink=lambda model, source_id=None: MagicMock(),
    )


def _agent() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        model_config_id=uuid4(),
        model_config=MagicMock(),
        config={"temperature": 0.7},
    )


def _hooks(*, payload: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(payload=payload or {})))


def test_linear_path_retrieves_in_short_session_then_commits_before_generate(monkeypatch):
    db = _TxnDb()
    short = _ShortSession()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_retrieve(*args, **kwargs):
        captured["retrieve_db"] = kwargs["db"]
        return [{"content": "片段", "score": 0.9}]

    async def fake_generate(**kwargs):
        db.events.append("generate")
        captured["generate_kwargs"] = kwargs
        return "答"

    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: short)
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(side_effect=fake_retrieve))
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(side_effect=fake_generate))

    out = _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="问题"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(),
        )
    )

    assert out.answer == "答"
    # 检索走的是短会话，不是请求会话
    assert captured["retrieve_db"] is short
    assert short.entered == 1
    # 顺序：先 commit 请求会话，再进入生成
    assert db.events == ["commit", "generate"]
    # 生成入口拿到的是 hits，不拿 db
    assert captured["generate_kwargs"]["prompt"].endswith("问题")
    assert "db" not in captured["generate_kwargs"]


def test_linear_path_media_reader_is_short_session_reader(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: _ShortSession())
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(return_value=[]))
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(return_value="答"))

    _run(AgentChatRagMixin.rag_chat(svc, _agent(), ChatRequest(query="问题"), ["kb1"], 5, uuid4(), _hooks()))

    reader = chat_rag_mod.generate_rag_answer.await_args.kwargs["media_reader"]
    assert isinstance(reader, FlowMediaReader)


def test_linear_path_keeps_retrieve_query_and_prompt_query_distinct(monkeypatch):
    """回归：检索用 retrieve_query、prompt 用 prompt_query，两者不得对调。

    当 BEFORE_CALL Hook 把 query 改写成空白、且带附图时，两条用途会真正分叉：
    retrieve_query 兜底为 body.query，prompt_query 兜底为附图文案。
    """
    db = _TxnDb()
    short = _ShortSession()
    svc = _svc(db, media_query="请根据附图回答。")
    captured: dict[str, object] = {}

    async def fake_retrieve(query, **kwargs):
        captured["search"] = query
        return []

    def fake_build_prompt(**kwargs):
        captured["prompt_kwargs"] = kwargs
        return "拼好的 prompt"

    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: short)
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(side_effect=fake_retrieve))
    monkeypatch.setattr(chat_rag_mod, "build_rag_prompt", fake_build_prompt)
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(return_value="答"))

    _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="原始问题"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(payload={"query": "   "}),
        )
    )

    assert captured["search"] == "原始问题"
    assert captured["prompt_kwargs"]["query"] == "请根据附图回答。"


def test_graph_path_commits_before_workflow(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)

    async def fake_workflow(**kwargs):
        db.events.append("workflow")
        return "答", [], []

    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: True)
    monkeypatch.setattr(chat_rag_mod, "run_rag_workflow", AsyncMock(side_effect=fake_workflow))

    _run(AgentChatRagMixin.rag_chat(svc, _agent(), ChatRequest(query="问题"), ["kb1"], 5, uuid4(), _hooks()))

    assert db.events == ["commit", "workflow"]
    reader = chat_rag_mod.run_rag_workflow.await_args.kwargs["media_reader"]
    assert isinstance(reader, FlowMediaReader)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_chat_rag_connection_release.py -v`

Expected: FAIL —— `AttributeError: module ... does not have the attribute 'generate_rag_answer'`（L1 尚未 import），且 `db.events` 里没有 `"commit"`。

- [ ] **Step 3: 改 import 与 media_reader**

`chat_rag.py` 顶部把 media reader 的 import 换成两个构造函数：

```python
from miles_portal.tenant.attachments.services.media_reader import (
    build_flow_media_reader,
    build_session_media_reader,
)
```

`miles_ai.rag.generate` 的 import 加入新符号（`rag_answer` 此时已无调用方，先删除它，Task 6 再清理导出）：

```python
from miles_ai.rag.generate import build_rag_prompt, format_hits_context, generate_rag_answer, retrieve_hits
```

加入短会话工厂：

```python
from miles_core.infra.db import AsyncSessionLocal
```

`resolve_chat_media_parts`（`chat_rag.py:155`）改用短会话读取器：

```python
    async def resolve_chat_media_parts(self, agent: Agent, body: ChatRequest) -> tuple[str, list]:
        """解析附图，返回生成用 query 文本与 multimodal content parts。

        用短会话读取器：本方法只读对象存储，不该借用请求会话——否则对象存储 I/O
        期间请求事务一直开着（两条 RAG 路径与直连路径都会调用本方法）。
        """
        max_media = int((agent.config or {}).get("max_media_per_turn", 10))
        parts: list = []
        if body.media:
            parts = await resolve_media_refs(
                build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                body.media,
                max_count=max_media,
            )
        query = body.query.strip() or ("请根据附图回答。" if parts else body.query.strip())
        return query, parts
```

> `build_session_media_reader` 仍被 `_run_tool_agent`（`chat_rag.py:281`）使用，import 保留；`_run_tool_agent` 本轮不改（见设计 §7）。

- [ ] **Step 4: 改两条生成分支**

把 `if should_use_langgraph_rag(agent, kb_ids=kb_ids):` 起的分支替换为：

```python
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                # 释放请求事务：检索由 retrieve 节点自开短会话完成，生成阶段不再需要本会话。
                await self.db.commit()
                answer, all_hits, steps = await run_rag_workflow(
                    model=model,
                    system_prompt=base,
                    query=retrieve_query,
                    prompt_query=prompt_query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
                    agent_id=agent_id,
                    top_k=top_k,
                    temperature=temperature,
                    agent_config=agent.config or {},
                    conversation_id=body.conversation_id,
                    media=body.media or None,
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                    bindings=kb_bindings,
                    media_reader=build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                )
            else:
                # 检索必须在 L1 用短会话完成，否则它会在生成入口内部重新打开请求事务，
                # 使「生成期间不占连接」失效。retrieve_query 用于检索、prompt_query 写入 prompt。
                search_q = (retrieve_query if retrieve_query is not None else prompt_query).strip()
                async with AsyncSessionLocal() as search_db:
                    linear_hits = await retrieve_hits(
                        search_q,
                        tenant_id=agent.tenant_id,
                        kb_ids=kb_ids,
                        db=search_db,
                        top_k=top_k,
                        bindings=kb_bindings,
                    )
                await self.db.commit()
                prompt = build_rag_prompt(system_prompt=base, query=prompt_query, hits=linear_hits)
                answer = await generate_rag_answer(
                    model=model,
                    prompt=prompt,
                    media=body.media or None,
                    media_reader=build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                    temperature=temperature,
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                )
                all_hits = linear_hits
                steps = [{"type": "rag_linear", "engine": "langchain"}]
```

同时把 `rag_chat` 的 docstring 里 `` `rag_answer` `` 改成 `` `generate_rag_answer` ``，以及 `service.py:10` 的说明同步（`rag_chat` → LangGraph 或线性 `generate_rag_answer`）。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_chat_rag_connection_release.py -v`

Expected: PASS。

- [ ] **Step 6: 跑受影响测试与门禁**

Run:
```bash
uv run --all-packages --group dev python -m pytest tests/tenant/agents tests/rag tests/flow -q && \
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 7: 变异测试（确认护栏有效）**

临时删掉线性分支的 `await self.db.commit()`，重跑 Step 1 的测试，确认 `test_linear_path_retrieves_in_short_session_then_commits_before_generate` **失败**；再临时把 `retrieve_hits` 的 `db=search_db` 改成 `db=self.db`，确认**失败**；然后还原。

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_chat_rag_connection_release.py -q`

Expected（两种变异态）：FAIL。还原后 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py \
        backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/service.py \
        backend/tests/tenant/agents/test_chat_rag_connection_release.py
git commit -F - <<'EOF'
feat(agents): RAG 生成前释放请求会话连接

请求事务从 agent 加载开始一直开到请求出口，LLM 调用夹在中间，单个对话
在整个生成期间占住一个连接（池 15、超时 30s），并发接近上限时后续请求
只能等满超时。

两条「检索→生成」路径打通：线性路径的检索移到 L1 并用短会话完成，随后提交
请求事务、以无 db 的 generate_rag_answer 生成；LangGraph 路径的检索节点本就
自开短会话，调用前提交即可。附图解析改为短会话读取器，不再借用请求会话。

前置读与 BEFORE_CALL 的 hook 日志因此提前落库、不再随本轮回滚——这是提前
收尾连接的必然取舍，方向与此前「失败审计自己提交」一致。
EOF
```

---

### Task 6: 删除组合入口 `rag_answer`

**为什么：** 拆分后它已无生产调用方（只剩测试引用），留着会成为只被测试引用的死代码。

**Files:**
- Modify: `backend/packages/miles-ai/src/miles_ai/rag/generate/answer.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/rag/generate/__init__.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/__init__.py`
- Modify: `backend/tests/rag/test_rag_answer_stream.py`
- Modify: `backend/tests/rag/test_rag_multimodal.py`
- Modify: `backend/packages/miles-ai/src/miles_ai/rag/generate/context.py`（docstring 提及）
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/langchain/chat_models.py`（docstring 提及）
- Modify: `backend/packages/miles-ai/src/miles_ai/integrations/langgraph/runner.py`（docstring 提及）

**Interfaces:**
- Consumes: `retrieve_hits` + `build_rag_prompt` + `generate_rag_answer`（Task 3）
- Produces: `rag_answer` 从 `answer.py`、`rag/generate/__init__.py`、两个惰性 shim 中彻底移除；不再有任何符号叫 `rag_answer`

- [ ] **Step 1: 迁移测试（先迁移，后删除，保证每步可跑）**

`tests/rag/test_rag_answer_stream.py` 的 `test_rag_answer_forwards_on_delta` 改为直接测生成入口（检索已不在其职责内）：

```python
@pytest.mark.asyncio
async def test_generate_rag_answer_forwards_on_delta():
    seen: dict[str, object] = {}
    model = _model()

    async def fake_ainvoke(*args, **kwargs):
        seen["on_delta"] = kwargs.get("on_delta")
        return "ans"

    async def delta(_: str) -> None:
        pass

    with patch(
        "miles_ai.rag.generate.answer.ainvoke_chat",
        new_callable=AsyncMock,
        side_effect=fake_ainvoke,
    ):
        answer = await generate_rag_answer(model=model, prompt="p", on_delta=delta)

    assert answer == "ans"
    assert seen["on_delta"] is delta
```

import 行相应改为：

```python
from miles_ai.rag.generate.answer import generate_rag_answer
```

> 「检索用 `retrieve_query`、prompt 用 `prompt_query`」的回归已在 Task 5 的 `test_linear_path_keeps_retrieve_query_and_prompt_query_distinct` 覆盖（该映射在 L1，本文件不重复）。

`tests/rag/test_rag_multimodal.py` 的 `test_rag_answer_media_without_reader_raises` **删除**（连同文件顶部 `from miles_ai.rag.generate.answer import rag_answer` 这一行）：等价覆盖已在 Task 3 新增的 `tests/rag/test_generate_rag_answer.py::test_generate_rag_answer_with_media_without_reader_raises`，且该节点级用例（`test_generate_node_with_media_without_reader_raises` / `test_fallback_node_with_media_without_reader_raises`）仍在，保留会造成三处重复。删掉后确认 `pytest` / `BadRequestError` / `MediaRefIn` 在该文件仍有其他使用点。

- [ ] **Step 2: 跑测试确认通过（此时删除尚未发生）**

Run: `uv run --all-packages --group dev python -m pytest tests/rag -v`

Expected: PASS。

- [ ] **Step 3: 删除 `rag_answer`**

从 `answer.py` 删除整个 `rag_answer` 函数；删除后确认 `AsyncSession` / `retrieve_hits` 的 import 仍被 `retrieve_hits` 自身使用（`retrieve_hits` 保留），`KbRetrievalBindings` 亦然。

`rag/generate/__init__.py` 改为：

```python
"""
RAG 生成子包（L2，线性路径）。

导出
----
- ``retrieve_hits``：多 KB 检索（画布、LangGraph retrieve 节点）
- ``build_rag_prompt`` / ``generate_rag_answer``：拼 prompt + 生成（生成阶段无 db）
- ``format_hits_context`` / ``build_rag_user_prompt``：拼 LLM 输入

Agent 默认多轮 RAG 图见 ``integrations.langgraph.graphs.rag_qa``，非本包。
"""

from miles_ai.rag.generate.answer import (
    build_rag_prompt,
    generate_rag_answer,
    retrieve_hits,
)
from miles_ai.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_prompt",
    "build_rag_user_prompt",
    "format_hits_context",
    "generate_rag_answer",
    "retrieve_hits",
]
```

`integrations/langchain/__init__.py`：`__all__` 删除 `"rag_answer"`；`__getattr__` 元组删除 `"rag_answer"`。

`integrations/__init__.py`：`__all__` 删除 `"rag_answer"`；`__getattr__` 元组删除 `"rag_answer"`。

改 `context.py:33`、`chat_models.py:7`、`runner.py:15` 的 docstring：把 `rag_answer` 的提及替换为 `generate_rag_answer`（措辞保持原义）。

- [ ] **Step 4: 全仓确认无残留**

Run:
```bash
grep -rn "rag_answer" --include=*.py backend/ | grep -v "generate_rag_answer"
```
Expected: 无输出（`generate_rag_answer` 匹配已被 `grep -v` 排除）。

- [ ] **Step 5: 门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add backend/packages/miles-ai/src/miles_ai/rag/generate/answer.py \
        backend/packages/miles-ai/src/miles_ai/rag/generate/__init__.py \
        backend/packages/miles-ai/src/miles_ai/rag/generate/context.py \
        backend/packages/miles-ai/src/miles_ai/integrations/__init__.py \
        backend/packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py \
        backend/packages/miles-ai/src/miles_ai/integrations/langchain/chat_models.py \
        backend/packages/miles-ai/src/miles_ai/integrations/langgraph/runner.py \
        backend/tests/rag/test_rag_answer_stream.py \
        backend/tests/rag/test_rag_multimodal.py
git commit -F - <<'EOF'
refactor(rag): 删除已无生产调用方的 rag_answer 组合入口

检索移到 L1 后，rag_answer 只剩「检索 + 生成」的粘合，且生产侧已无调用方，
保留只会成为仅测试引用的死代码，其 db 参数也会重新打开「生成期间持有连接」
的口子。测试改为直接覆盖 retrieve_hits + build_rag_prompt + generate_rag_answer
的组合，并显式钉住 retrieve_query / prompt_query 不得对调。
EOF
```

---

### Task 7: 直连对话同样在生成前释放连接

> **范围说明（用户已裁决 2026-09-14：保留本 Task）**：本 Task 超出 spec 字面范围的「两条检索→生成路径」，但 `direct_chat` 是同一形态（单次 LLM 调用、边界清晰）、同一缺陷（`resolve_invoke_model` 读租户凭据已开事务，随后 LLM 期间一直占据一个连接）。用户已确认纳入。

**为什么：** `direct_chat`（无 KB 直连）同样在 `ainvoke_chat` 期间持有请求事务：`resolve_invoke_model` 会读库（`load_tenant_credential`），事务已开。

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py`（`direct_chat`，约 194-200 行）
- Modify: `backend/tests/tenant/agents/test_chat_rag_connection_release.py`

**Interfaces:**
- Consumes: Task 5 已在 `chat_rag.py` 引入的 `AsyncSessionLocal`（本 Task 不新增 import）
- Produces: `direct_chat` 在 `ainvoke_chat` 前 `commit` 请求会话，完成后行为不变

- [ ] **Step 1: 写失败测试**

在 `backend/tests/tenant/agents/test_chat_rag_connection_release.py` 追加：

```python
def test_direct_chat_commits_before_llm(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_ainvoke(model, messages, **kwargs):
        db.events.append("llm")
        captured["messages"] = messages
        return "答"

    monkeypatch.setattr(chat_rag_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))

    out = _run(
        AgentChatRagMixin.direct_chat(
            svc,
            _agent(),
            ChatRequest(query="问题"),
            uuid4(),
            _hooks(),
        )
    )

    assert out.answer == "答"
    assert db.events == ["commit", "llm"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_chat_rag_connection_release.py::test_direct_chat_commits_before_llm -v`

Expected: FAIL —— `assert [] == ['commit', 'llm']`。

- [ ] **Step 3: 在 `direct_chat` 的 LLM 调用前提交**

`chat_rag.py` 中 `direct_chat` 的这段：

```python
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            answer = await ainvoke_chat(
```

改为：

```python
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            # 释放请求事务：模型解析会读租户凭据，随后是单次 LLM 调用，中间无需本会话。
            await self.db.commit()
            answer = await ainvoke_chat(
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/agents/test_chat_rag_connection_release.py -v`

Expected: PASS。

- [ ] **Step 5: 门禁**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py \
        backend/tests/tenant/agents/test_chat_rag_connection_release.py
git commit -F - <<'EOF'
feat(agents): 直连对话在 LLM 前释放请求会话连接

直连路径的模型解析会读租户凭据，事务因此已开，随后单次 LLM 调用期间一直占着
一个连接——与 RAG 路径是同一个缺陷，只是没有检索这一步。

在 ainvoke_chat 前提交请求事务；调用记录与 hook 日志仍走出口事务。
EOF
```

---

### Task 8: 收尾——全量门禁、结构护栏复核、回填 spec 修订记录

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-rag-generation-db-connection-design.md`（§9 修订记录）

**Interfaces:**
- Consumes: Task 1-7 的全部产物
- Produces: 一份与实际实现一致的 spec 修订记录

- [ ] **Step 1: 复核两个结构不变量**

Run:
```bash
cd backend && uv run --all-packages --group dev python -c "
import inspect
from miles_ai.rag.generate.answer import generate_rag_answer
from miles_portal.tenant.models.services.usage import ChatUsageSink
print('generate_rag_answer:', list(inspect.signature(generate_rag_answer).parameters))
print('ChatUsageSink:', list(inspect.signature(ChatUsageSink.__init__).parameters))
"
```
Expected: 两个参数列表里都**没有** `db`。

- [ ] **Step 2: 全量门禁（CI 同款五条）**

Run:
```bash
uv run --all-packages --group dev ruff format --check . && \
uv run --all-packages --group dev ruff check . && \
uv run --all-packages --group dev lint-imports && \
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check && \
uv run --all-packages --group dev python -m pytest -q
```
Expected: 全绿，且 OpenAPI 快照**零漂移**（未改对外契约）。

- [ ] **Step 3: 回填 spec 修订记录**

把 spec 的 `## 9. 修订记录` 一节替换为：

```markdown
## 9. 修订记录

### 2026-09-14：实施落地

1. **§4.2③ 收口**：原表述「`rag_answer` 新增可选 `hits`、`db` 变为可选」无法把「生成函数没有 db」落到签名上，改为「抽出无 db 的 `generate_rag_answer` + 删除组合入口 `rag_answer`」。
2. **§8.1 结论**：`_chat_usage_acc` ContextVar 的实际行为见 `tests/tenant/agents/test_rag_usage_accumulation.py`（该测试即结论载体）。
3. **范围外补充**：`direct_chat`（无 KB 直连）同属「LLM 单次调用期间持有连接」，已一并处理，见 §7 非目标清单的边界说明。
4. **附图读取处数**：实际改动 3 处（`resolve_chat_media_parts` 与两条生成分支），`_run_tool_agent` 未改。
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-14-rag-generation-db-connection-design.md
git commit -F - <<'EOF'
docs(agents): 回填生成阶段释放连接设计的实施修订记录

记录三处与设计原稿的差异：生成入口改为无 db 的 generate_rag_answer 并删除
组合入口、ContextVar 结论的载体测试、以及直连路径一并处理。
EOF
```

---

## 自检记录

**Spec 覆盖核对（逐节）**

| spec 章节 | 对应 Task |
|---|---|
| §3 目标（生成阶段不持有连接） | Task 5（L1 提交 + 短会话检索）、Task 3（签名无 db）、Task 7（直连） |
| §3 不变量 1/2（answer / hits / steps、retrieve_query vs prompt_query） | Task 3（`build_rag_prompt` 分支测试）、Task 5（L1 编排 + `retrieve_query`/`prompt_query` 分叉回归） |
| §3 不变量 3（用量计量口径） | Task 2（`get_chat_usage_totals` 断言保留）、Task 1（ContextVar 探针） |
| §3 不变量 4（出口收尾不变） | 未改动出口；Task 5 只新增生成前 commit |
| §3 新增不变量（签名无 db） | Task 2（sink）、Task 3（生成入口）均有 `inspect.signature` 断言 |
| §4.2① `ChatUsageSink` 自开短会话 + 删 db | Task 2 |
| §4.2② `chat_rag` 编排 + media_reader | Task 5 |
| §4.2③ 生成入口去 db、检索移 L1 | Task 3 + Task 5 |
| §4.2④ `rag_qa` 去重 | Task 4 |
| §4.4 语义变化（前置读提前落库） | Task 5 commit message 显式记录 |
| §4.4 commit 失败不吞 | Task 5 不包 try/except（Step 4 代码即证据） |
| §5 验收 1-8 | 分别落在 Task 2/3/5/6/4/8 |
| §7 非目标（tool agent 不改） | Task 5 Step 3 注释显式说明 `_run_tool_agent` 保留 session reader |
| §8.1 ContextVar | Task 1（只诊断；按结论二选一：原地累加修复 + 回归测试，或固化实测行为） |
| §8.2 附图读两遍 | 文档已声明不承诺；无任务（符合 spec） |

**占位符扫描**：无 TBD / TODO / 「类似 Task N」；每个改动步骤均给出完整代码。

**执行前裁决（2026-09-14，用户确认）**：
1. 实施位置：worktree `.worktrees/rag-generation-db-connection`（分支 `feat/rag-generation-db-connection`），不在 `main` 上直接改。
2. Task 7（直连 `direct_chat`）保留。
3. Task 1 改为「只诊断」：探针脚本放 `/tmp`（一次性脚本不进仓库），按结论二选一（修复 or 固化），**不提交**断言破损行为的测试。

**类型一致性**：`generate_rag_answer` 的签名在 Task 3 定义（`model/prompt/media/media_reader/temperature/on_delta/usage_sink`），Task 4、5、6、7 的调用与测试全部使用同名同形参；`build_rag_prompt(*, system_prompt, query, hits)` 在 Task 3 定义，Task 4/5/6 一致；`ChatUsageSink(*, tenant_id, model, source_id)` 在 Task 2 定义，3 处构造点一致。
