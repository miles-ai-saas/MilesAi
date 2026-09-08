# B-1 实施计划：对话/画布 LLM 调用链的模型解析与用量记录依赖反转

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/`（chat_models、litellm adapter、tool_agent loop、langgraph runner/graph、deepagents orchestrator）与 `flow_runtime/nodes/llm_nodes.py` 对 `app.tenant.models.services.{model_resolve,usage}` 的反向 import，把"按租户解析可用模型 + Token 用量记录"职责收敛到 L1 装配点。

**Architecture:** 采用 **L1 装配 + 注入**：L3 引擎不再接收 `db/tenant_id` 自行解析与记录，而是接收"已解析的 `ModelConfig`"与一个中立 `UsageSink`（仅含 `record(prompt_tokens, completion_tokens)` 的 L3 协议）。L1（`AgentService`、flow 运行入口）负责：解析模型一次、构造 `ChatUsageSink` 传入。flow 画布因节点可按 `model_config_id` 覆盖模型，改走 **回调注入**：`RunContext` 携带 `resolve_model` 回调（L1 注入，内部自开会话解析），节点不再 import resolver。

**Tech Stack:** FastAPI / SQLAlchemy async / LiteLLM / LangChain / LangGraph（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`integrations`（L3）禁止 import `tenant`（L1）；允许 `tenant → integrations` 单向。本计划收敛后，`chat_models.py`、`adapter.py`、`tool_agent/loop.py`、`langgraph/runner.py`、`langgraph/graphs/rag_qa.py`、`deepagents/orchestrator.py`、`flow_runtime/nodes/llm_nodes.py` 不得再出现 `app.tenant.models.services` import。
- 中文 docstring（README §文档注释）：新增/改动模块须写模块与公开方法 docstring。
- 体量：改动文件不得超过 500 行；单文件 ≥400 行新增逻辑优先拆文件。
- 语义保持：迁移不得改变现有行为——用量日志行、chat usage 累计（contextvar）、报错文案均须保持不变。
- 测试：每任务结束跑指定 pytest 文件 + 全量回归（`pytest -q` 430 基线），本计划所有任务完成后全量仍应通过；不允许为了过测试修改非本计划文件的语义。
- 提交：每任务单独 commit，message 简体中文，`<type>(<scope>): <简述>`。

---

### Task 1: L3 中立 `UsageSink` 协议 + litellm adapter 参数化

**Files:**
- Create: `backend/app/integrations/litellm/usage_sink.py`
- Modify: `backend/app/integrations/litellm/adapter.py`

**Interfaces:**
- Produces（供 Task 2/4 使用）:
  - `UsageSink`：`@runtime_checkable` Protocol，唯一方法 `async def record(self, *, prompt_tokens: int, completion_tokens: int) -> None`
  - `litellm_chat_completion_stream(...)` / `litellm_chat_completion(...)` 的参数 `usage_ctx: Any | None` → 改名 `usage_sink: UsageSink | None`，行为不变（None 时不记录）

- [ ] **Step 1: 新建协议文件**

`backend/app/integrations/litellm/usage_sink.py`：

```python
"""LiteLLM 用量记录回调（L3 中立，不依赖 tenant 域）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UsageSink(Protocol):
    """一次对话/工具调用的 Token 用量记录器。

    由 L1 装配实现（如 ``tenant.models.services.usage.ChatUsageSink``）并
    随引擎调用注入；adapter 只调用本协议，不感知落库/累计细节。
    """

    async def record(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        ...
```

- [ ] **Step 2: adapter 参数化并移除 tenant import**

`backend/app/integrations/litellm/adapter.py`：

顶部（litellm import 附近）新增：

```python
from app.integrations.litellm.usage_sink import UsageSink
```

改动两处函数签名（原 `usage_ctx: Any | None = None` → `usage_sink: UsageSink | None = None`）。文件内两处记录点（stream 路径约 L212-221、非流路径约 L271-279，形如）：

```python
    if usage_ctx is not None and usage_response is not None:
        prompt_t, completion_t, _ = _extract_usage(usage_response)
        from app.tenant.models.services.usage import record_model_usage

        await record_model_usage(
            usage_ctx,
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
        )
```

改为：

```python
    if usage_sink is not None and usage_response is not None:
        prompt_t, completion_t, _ = _extract_usage(usage_response)
        await usage_sink.record(
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
        )
```

非流路径（`usage_response` 即 `response`）同步改；函数内 `from app.tenant.models.services.usage import record_model_usage` 两处删除。

- [ ] **Step 3: 运行相关测试确认无回归**

Run: `cd backend && .venv/bin/python -m pytest tests/infra/test_litellm_adapter.py tests/infra/test_litellm_chat_stream.py -q`
Expected: PASS（现有用例基本不传 usage_ctx/sink，主要确认签名改名无破坏）

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/litellm/usage_sink.py backend/app/integrations/litellm/adapter.py
git commit -m "refactor(integrations): litellm 用量记录改为中立 UsageSink 协议注入"
```

---

### Task 2: L1 `ChatUsageSink` 实现

**Files:**
- Modify: `backend/app/tenant/models/services/usage.py`
- Test: `backend/tests/tenant/models/test_chat_usage_accumulation.py`（扩展；原文件仅测 contextvar，不测 sink）

**Interfaces:**
- Consumes: Task 1 的 `UsageSink` 协议
- Produces（供 Task 3-9）:
  - `ChatUsageSink(db, tenant_id, model, source_id=None)`，其 `record(prompt_tokens, completion_tokens)` 复刻原 `record_model_usage` 行为（chat 累计 contextvar + 写 `ModelUsageLog` + flush）
  - 保留既有 `UsageRecordContext` / `record_model_usage` / `record_litellm_response_usage` / `begin|end|get_chat_usage_accumulation` API（兼容存量引用，直至 Task 6 完成后再清理）

- [ ] **Step 1: 在 usage.py 追加 `ChatUsageSink`**

`backend/app/tenant/models/services/usage.py` 文件底部新增：

```python
class ChatUsageSink:
    """对话链路的用量记录器：会话 token 累计 + 落 ModelUsageLog。

    实现 L3 ``UsageSink`` 协议，由 L1 装配（如 AgentService、flow 运行入口）
    构造并注入引擎；``source_id`` 为对话 agent_id，用于 chat 用量累计。
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        model: ModelConfig,
        source_id: UUID | None = None,
    ) -> None:
        self._ctx = UsageRecordContext(
            db=db,
            tenant_id=tenant_id,
            model=model,
            source="chat",
            source_id=source_id,
        )

    async def record(self, *, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        await record_model_usage(
            self._ctx,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
```

顶部导入不动（`AsyncSession`、`UUID`、`ModelConfig` 均已 import）。

- [ ] **Step 2: 扩展单测验证 record 走累计 + 落库**

`backend/tests/tenant/models/test_chat_usage_accumulation.py` 追加（先读现有文件结构，保持风格；使用 async 测试装饰器）：

```python
from uuid import uuid4

import pytest

from app.models.model import ModelConfig
from app.tenant.models.services.usage import ChatUsageSink, begin_chat_usage_accumulation, get_chat_usage_totals


@pytest.mark.asyncio
async def test_chat_usage_sink_accumulates_and_flushes(db_session):
    begin_chat_usage_accumulation()
    sink = ChatUsageSink(
        db=db_session,
        tenant_id=uuid4(),
        model=ModelConfig(name="m", provider="openai", model_name="x"),
        source_id=uuid4(),
    )
    await sink.record(prompt_tokens=100, completion_tokens=20)
    assert get_chat_usage_totals() == (100, 20)
```

（`db_session` fixture：先 `rg -l "def db_session" tests` 定位全仓 async 会话 fixture，选用 tests/ 根 conftest 或 tenant/models conftest 提供者；确保是 async fixture。）

- [ ] **Step 3: 运行该文件测试**

Run: `cd backend && .venv/bin/python -m pytest tests/tenant/models/test_chat_usage_accumulation.py -q`
Expected: 全部通过（含新用例）

- [ ] **Step 4: Commit**

```bash
git add backend/app/tenant/models/services/usage.py backend/tests/tenant/models/test_chat_usage_accumulation.py
git commit -m "feat(agents): 新增 ChatUsageSink 用量记录器实现 L3 UsageSink 协议"
```

---

### Task 3: `AgentService` 装配门面：`resolve_invoke_model` / `chat_usage_sink`

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`（`AgentChatRagMixin` 追加两个方法）
- Test: 无独立新测试；依赖 Task 5-9 集成验证

**Interfaces:**
- Consumes: `usage.ChatUsageSink`、`model_resolve.resolve_model_for_invoke`
- Produces（供 Task 4-9 中所有需要"预解析 + 用量记录"的 L3/L1 调用点使用，L3 通过已注入的 `svc` 鸭子访问，不 import）:
  - `async def resolve_invoke_model(self, model: ModelConfig | None) -> ModelConfig`
  - `def chat_usage_sink(self, model: ModelConfig, *, source_id: UUID | None = None) -> ChatUsageSink`

- [ ] **Step 1: 在 `AgentChatRagMixin` 追加两方法**

`backend/app/tenant/agents/services/agent/chat_rag.py` 顶部 import 区补：

```python
from app.tenant.models.services.model_resolve import resolve_model_for_invoke
from app.tenant.models.services.usage import ChatUsageSink
```

类内追加（`self.db` / `self.ctx` 由 `BaseService` 提供）：

```python
    async def resolve_invoke_model(self, model: ModelConfig | None) -> ModelConfig:
        """按当前租户解析可用模型（合并 BYOK）；无模型时抛 ValueError。"""
        if model is None:
            raise ValueError("未配置可用模型")
        return await resolve_model_for_invoke(self.db, model, self.ctx.tenant_id)

    def chat_usage_sink(
        self,
        model: ModelConfig,
        *,
        source_id: UUID | None = None,
    ) -> ChatUsageSink:
        """构造注入引擎的用量记录器（chat 累计 + 落库）。"""
        return ChatUsageSink(
            db=self.db,
            tenant_id=self.ctx.tenant_id,
            model=model,
            source_id=source_id,
        )
```

`ModelConfig` 与 `UUID` 的 import 已在文件中存在则复用，否则补 `from uuid import UUID` 与 `from app.models.model import ModelConfig`。

- [ ] **Step 2: import 冒烟**

Run: `cd backend && .venv/bin/python -c "from app.tenant.agents.services.agent import AgentService; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "feat(agents): AgentService 提供模型解析与用量 sink 装配门面"
```

---

### Task 4: `ainvoke_chat` 去除 db/tenant 解析与用量装配

**Files:**
- Modify: `backend/app/integrations/langchain/chat_models.py`
- Test: `backend/tests/infra/test_litellm_chat_stream.py`、`backend/tests/rag/test_rag_answer_stream.py`（仅回归）

**Interfaces:**
- Consumes: Task 1 `UsageSink`
- Produces（供 Task 5-9）:
  - 新签名 `ainvoke_chat(model: ModelConfig, messages, *, temperature=0.7, max_tokens=2048, usage_sink: UsageSink | None = None, on_delta: OnDelta | None = None) -> str`。`model` 由调用方保证已 resolve；删除 `db/tenant_id/source_id` 参数。

- [ ] **Step 1: 改写 `ainvoke_chat`**

`backend/app/integrations/langchain/chat_models.py`：

1. 顶部 import 区新增：`from app.integrations.litellm.usage_sink import UsageSink`
2. `ainvoke_chat` 函数体替换为（删除两段 `if db is not None and tenant_id is not None:` 内对 `app.tenant.models.services.model_resolve` / `usage` 的延迟 import 与 resolve/构造，`usage_ctx` 改 `usage_sink`）：

```python
async def ainvoke_chat(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    usage_sink: UsageSink | None = None,
    on_delta: OnDelta | None = None,
) -> str:
    """
    异步对话（OpenAI 形状 ``{"role","content"}`` 列表）。

    ``model`` 须为调用方已解析（合并 BYOK）的配置；用量记录经
    ``usage_sink`` 注入（见 ``litellm.usage_sink.UsageSink``）。
    ``content`` 可为字符串或多模态 part 数组（见 ``integrations.chat.multimodal``）。
    """
    openai_msgs: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        openai_msgs.append({"role": role, "content": content})
    if on_delta is not None:
        return await litellm_chat_completion_stream(
            model,
            openai_msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            usage_sink=usage_sink,
            on_delta=on_delta,
        )
    return await litellm_chat_completion(
        model,
        openai_msgs,
        temperature=temperature,
        max_tokens=max_tokens,
        usage_sink=usage_sink,
    )
```

模块 docstring 首段"业务入口"说明同步更新：注明"调用方须先 resolve 模型；用量经 `usage_sink` 注入"。

- [ ] **Step 2: 回归测试确认编译**

Run: `cd backend && .venv/bin/python -m pytest tests/infra/test_litellm_chat_stream.py tests/rag/test_rag_answer_stream.py -q`
Expected: 失败或 import 错误属预期（存量调用方仍传 `db=`/`tenant_id=`），Task 5-9 会逐一迁移。**若失败仅因调用方旧参数**，属预期；记录当前失败清单供后续核对。

- [ ] **Step 3: Commit（此 commit 允许中间态——函数已改、调用方未全迁；若担心红，可把 Step 2 视作仅收集清单，不要求绿）**

```bash
git add backend/app/integrations/langchain/chat_models.py
git commit -m "refactor(integrations): ainvoke_chat 移除内部模型解析与用量装配"
```

---

### Task 5: 迁移 `chat_rag.direct_chat` 装配点

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Test: 依赖全量回归（此路径被 agents 对话用例覆盖，迁移后运行 `pytest -q` 时应恢复绿）

**Interfaces:**
- Consumes: Task 3 门面、Task 4 `ainvoke_chat` 新签名
- Produces: 无新接口（迁移完成 direct 路径）

- [ ] **Step 1: 改写 `direct_chat` 调用段**

现 `chat_rag.py` 中 `direct_chat`（约 L135）原形（Task 3 前）：

```python
            answer = await ainvoke_chat(
                agent.model_config,
                [
                    {"role": "system", "content": base},
                    user_msg,
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
                db=self.db,
                tenant_id=self.ctx.tenant_id,
                source_id=agent_id,
                on_delta=on_delta,
            )
```

改为（先经 Task 3 门面解析 + 建 sink 一次）：

```python
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            answer = await ainvoke_chat(
                model,
                [
                    {"role": "system", "content": base},
                    user_msg,
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
                usage_sink=usage_sink,
                on_delta=on_delta,
            )
```

- [ ] **Step 2: 运行 agents 对话相关测试**

Run: `cd backend && .venv/bin/python -m pytest tests/tenant/agents -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "refactor(agents): direct_chat 由装配点解析模型并注入用量 sink"
```

---

### Task 6: 迁移 `run_tool_calling_chat`（tool_agent loop）

**Files:**
- Modify: `backend/app/integrations/langchain/tool_agent/loop.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`（两处 `run_tool_calling_chat` 调用）
- Test: `pytest -q` 全量回归

**Interfaces:**
- Consumes: Task 1 `UsageSink` 协议、Task 3 门面
- Produces:
  - `run_tool_calling_chat(db, ctx, agent, body, *, agent_id, system_prompt, model: ModelConfig, usage_sink: UsageSink | None) -> ChatResponse`（新增 `model`/`usage_sink` 必/可选参数；删除函数体内部 `resolve_model_for_invoke` 与 `UsageRecordContext` 构造）
  - 内部用量记录：`record_litellm_response_usage(usage_ctx, response)` → 用 adapter 公开的 `extract_litellm_usage(response)` + `usage_sink.record`

- [ ] **Step 1: 改写 loop.py**

`backend/app/integrations/langchain/tool_agent/loop.py`：

1. 顶部 import 删除：
   `from app.tenant.models.services.model_resolve import resolve_model_for_invoke`
   `from app.tenant.models.services.usage import UsageRecordContext, record_litellm_response_usage`
   并新增：
   `from app.integrations.litellm.usage_sink import UsageSink`
   `from app.integrations.litellm.adapter import extract_litellm_usage`（若文件顶部尚未导入 adapter 符号，加在现有 import 区）
2. `run_tool_calling_chat` 签名加两个参数：

```python
async def run_tool_calling_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent: Agent,
    body: ChatRequest,
    *,
    agent_id: UUID,
    system_prompt: str,
    model: ModelConfig,
    usage_sink: UsageSink | None = None,
) -> ChatResponse:
```

3. 删除原头部：

```python
    model = await resolve_model_for_invoke(db, agent.model_config, ctx.tenant_id)
    usage_ctx = UsageRecordContext(
        db=db,
        tenant_id=ctx.tenant_id,
        model=model,
        source="chat",
        source_id=agent_id,
    )
```

（`model` 现由调用方传入；`usage_ctx` 全局替换为 `usage_sink` 传参。）
4. 工具轮记录点（约 L157）：

```python
        await record_litellm_response_usage(usage_ctx, response)
```

改为：

```python
        if usage_sink is not None:
            p, c, _ = extract_litellm_usage(response)
            await usage_sink.record(prompt_tokens=p, completion_tokens=c)
```

（保留对 `agent.model_config` 为空的既有 `ValueError` 守卫——现守卫在签名下方，改为校验 `model` 非空可删，但 agent.model_config 仍被工具名解析等处使用，勿删原语义。）

- [ ] **Step 2: 更新 chat_rag 两处调用**

`chat_rag.py` 中两处（`not kb_ids` 的 tool calling 分支 L206 与 `should_use_skill_tools_with_kb` 分支 L236）：

```python
                return await run_tool_calling_chat(
                    self.db,
                    self.ctx,
                    agent,
                    body,
                    agent_id=agent_id,
                    system_prompt=f"{base}{kb_hint}",
                )
```

改为（两处相同处理）：

```python
                model = await self.resolve_invoke_model(agent.model_config)
                usage_sink = self.chat_usage_sink(model, source_id=agent_id)
                return await run_tool_calling_chat(
                    self.db,
                    self.ctx,
                    agent,
                    body,
                    agent_id=agent_id,
                    system_prompt=f"{base}{kb_hint}",
                    model=model,
                    usage_sink=usage_sink,
                )
```

（该分支调用发生在确认 `agent.model_config_id` 之后，故 `agent.model_config` 非空；`resolve_invoke_model` 已含 None 守卫。）

- [ ] **Step 3: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（Task 4 引入的红应在本 Task 内通过 direct/tool 两路迁移消除；仍存在的红归因 Task 7-9 未迁点）

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/loop.py backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "refactor(agents): tool calling 循环改为装配点注入模型与用量 sink"
```

---

### Task 7: 迁移 RAG 链（`run_rag_workflow` / `rag_answer` / rag_qa 图节点）

**Files:**
- Modify: `backend/app/integrations/langgraph/runner.py`
- Modify: `backend/app/integrations/langgraph/graphs/rag_qa.py`（`generate` / `fallback` 两节点）
- Modify: `backend/app/rag/generate/answer.py`（`rag_answer`）
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`（`_rag_chat` 分支两路调用）

**Interfaces:**
- Consumes: Task 1 `UsageSink`、Task 3 门面
- Produces:
  - `run_rag_workflow(*, model, system_prompt, query, prompt_query, kb_ids, tenant_id, agent_id, top_k, temperature, thread_id, conversation_id, agent_config, media, user_id, on_delta, usage_sink: UsageSink | None = None)`：`model` 语义改为"已 resolve"；删除函数内 `AsyncSessionLocal` + `resolve_model_for_invoke` 段；把 `usage_sink` 写入 `run_config["configurable"]["usage_sink"]`
  - `rag_answer(..., usage_sink: UsageSink | None = None)`：`ainvoke_chat` 改传 `usage_sink`

- [ ] **Step 1: 改写 runner.run_rag_workflow**

`backend/app/integrations/langgraph/runner.py`：

1. 删除函数内两段（`run_rag_workflow` 内开 `AsyncSessionLocal` + `resolve_model_for_invoke` 的段）：

```python
    async with AsyncSessionLocal() as db:
        model = await resolve_model_for_invoke(db, model, tenant_id)
    ...
    run_config["configurable"]["model"] = model
```

改为：`model` 直接使用入参（调用方已 resolve），并在 `run_config["configurable"]` 追加 `usage_sink`：

```python
    run_config["configurable"]["model"] = model
    run_config["configurable"]["usage_sink"] = usage_sink
```

2. 签名新增 `usage_sink: UsageSink | None = None`；顶部 import 区：
   - 新增 `from app.integrations.litellm.usage_sink import UsageSink`
   - 删除函数内 `from app.tenant.models.services.model_resolve import resolve_model_for_invoke`（若存在）；保留模块级 `agents.constants.AgentRuntimeMode`（Task 10 前暂缓，属常量 import，非服务层）。

- [ ] **Step 2: 改写 rag_qa 的 generate/fallback**

`backend/app/integrations/langgraph/graphs/rag_qa.py` 两处（generate L198、fallback L251）：

```python
        answer = await ainvoke_chat(
            model,
            messages,
            temperature=float(state.get("temperature", 0.7)),
            db=db,
            tenant_id=UUID(state["tenant_id"]),
            source_id=UUID(state["agent_id"]) if state.get("agent_id") else None,
            on_delta=on_delta,
        )
```

改为（`model` 已 resolve，来自 `_cfg_model(config)`；`usage_sink` 取自 config）：

```python
        usage_sink = config["configurable"].get("usage_sink") if config else None
        answer = await ainvoke_chat(
            model,
            messages,
            temperature=float(state.get("temperature", 0.7)),
            usage_sink=usage_sink,
            on_delta=on_delta,
        )
```

（两节点结构相同；`db` 仍为节点内自开的 `AsyncSessionLocal`，仅用于媒体解析，保留。`UUID`/`db` 若因此不再使用则清理该节点未用变量——注意 `build_invoke_messages_with_media` 仍用 `db`，勿删。）

- [ ] **Step 3: 改写 rag_answer**

`backend/app/rag/generate/answer.py`：`rag_answer` 签名新增 `usage_sink: UsageSink | None = None`（顶部 import `app.integrations.litellm.usage_sink.UsageSink`）；内部 `ainvoke_chat` 调用改为：

```python
    answer = await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        usage_sink=usage_sink,
        on_delta=on_delta,
    )
```

（删除 `db=`/`tenant_id=`/`source_id=`；`model` 语义更新为已 resolve——docstring 注明。）

- [ ] **Step 4: 更新 chat_rag `_rag_chat` 分支**

`chat_rag.py` L260-293 区域：`_rag_chat` 中两路调用（`run_rag_workflow` 与 `rag_answer`）前先统一解析 + sink：

在 `if should_use_langgraph_rag(...):` 之前插入：

```python
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
```

然后：

- `run_rag_workflow(model=model, ..., usage_sink=usage_sink)`（删原 `model=agent.model_config`）
- `rag_answer(model=model, ..., usage_sink=usage_sink, ...)`（删原 `db=self.db`、`source_id=agent_id`；`rag_answer` 其它参数保留）

- [ ] **Step 5: 运行 RAG 相关测试**

Run: `cd backend && .venv/bin/python -m pytest tests/rag tests/tenant/agents -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrations/langgraph/runner.py backend/app/integrations/langgraph/graphs/rag_qa.py backend/app/rag/generate/answer.py backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "refactor(agents): RAG 链改为装配点解析模型并透传用量 sink"
```

---

### Task 8: 迁移 flow 画布链（`llm_nodes` 回调注入）

**Files:**
- Modify: `backend/app/flow_runtime/types.py`（`RunContext`）
- Modify: `backend/app/flow_runtime/nodes/llm_nodes.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`（`flow_run_context` 装配，定义于 `AgentChatRagMixin`）
- Modify: `backend/app/tenant/flows/services/flow.py`（调试运行 `RunContext` 构造）

**Interfaces:**
- Consumes: Task 1 `UsageSink`、Task 3 门面（agent 链）；flow 链经新 helper
- Produces:
  - `RunContext` 新增可选字段 `resolve_model: Callable[[str], Awaitable[ModelConfig]] | None = None` 与 `usage_sink: Any = None`
  - helper（L1）`backend/app/tenant/flows/services/run_context.py`：`make_flow_model_resolver(tenant_id) -> Callable[[str], Awaitable[ModelConfig]]`（内部 `AsyncSessionLocal` + 查 `ModelConfig` active + `resolve_model_for_invoke`）
  - `llm_nodes.llm_call` 不再 import `model_resolve`；改用 `ctx.resolve_model(model_id)`

- [ ] **Step 1: RunContext 加字段**

`backend/app/flow_runtime/types.py`：在 `RunContext` dataclass 增加（带默认值，保持旧构造兼容）：

```python
    # 画布 LLM 节点按 model_config_id 解析可用模型的回调（L1 注入；None 表示不支持）
    resolve_model: Callable[[str], Awaitable[ModelConfig]] | None = None
    # 画布 LLM 调用用量记录（L1 注入；None 表示不记录）
    usage_sink: Any = None
```

（顶部补 `Callable`/`Awaitable` import；`ModelConfig` 用 TYPE_CHECKING 或直接 import `app.models.model`——types.py 属 flow_runtime，import models 为 L3→models 允许。）

- [ ] **Step 2: 新建 L1 helper**

Create `backend/app/tenant/flows/services/run_context.py`：

```python
"""Flow 运行上下文装配：为画布节点注入模型解析与用量回调。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.common.exceptions import BadRequestError
from app.core.soft_delete import not_deleted
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.models.model import ModelConfig
from app.models.model.catalog import ModelPublishStatus
from app.tenant.models.services.model_resolve import load_tenant_credential, resolve_model_for_invoke
from app.tenant.models.services.usage import ChatUsageSink


def make_flow_model_resolver(tenant_id: UUID) -> Callable[[str], Awaitable[ModelConfig]]:
    """构造按 ``model_config_id`` 解析可用模型的回调（自开会话，合并 BYOK）。"""

    async def _resolve(model_id: str) -> ModelConfig:
        async with AsyncSessionLocal() as db:
            model = (
                await db.execute(
                    select(ModelConfig).where(
                        ModelConfig.id == UUID(model_id),
                        ModelConfig.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if not model:
                raise BadRequestError("模型配置不存在或已禁用")
            return await resolve_model_for_invoke(db, model, tenant_id)

    return _resolve
```

（`load_tenant_credential`/`ModelPublishStatus`/`not_deleted` 若未实际使用则不导入；本 helper 的核心语义与 `llm_nodes.llm_call` 原解析逻辑一致。）

- [ ] **Step 3: 改写 llm_nodes**

`backend/app/flow_runtime/nodes/llm_nodes.py`：
1. 删除 import：`from app.tenant.models.services.model_resolve import resolve_model_for_invoke`；删除 `select`/`ModelConfig`/`AsyncSessionLocal` 中仅为解析模型使用的部分（媒体解析仍用 `AsyncSessionLocal` 开库——若媒体分支用到 db 则保留 db 段，仅去掉模型查询与 resolve）。
2. `model_id` 解析段原：

```python
    async with AsyncSessionLocal() as db:
        model = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == model_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not model:
            raise BadRequestError("模型配置不存在或已禁用")
        model = await resolve_model_for_invoke(db, model, UUID(str(ctx.tenant_id)))
```

改为（在 `async with` 之前完成，model_id 为 str）：

```python
    if ctx.resolve_model is None:
        raise BadRequestError("运行上下文未提供模型解析回调")
    model = await ctx.resolve_model(str(model_id))
```

媒体解析部分（`resolve_media_refs(db, tenant_ctx, ...)`）仍需要 db，把 `async with AsyncSessionLocal() as db:` 保留在媒体段并下移缩进——**小心缩进**：若模型查询与媒体解析原在同一 `async with` 内，则把模型解析移出块、块内仅保留媒体相关行。
3. `ainvoke_chat` 调用处去掉 `db=`/`tenant_id=`，新增 `usage_sink=ctx.usage_sink`。

- [ ] **Step 4: 装配 flow 运行入口**

`chat_rag.py` 的 `flow_run_context`（返回 RunContext 处）与 `flows/service.py` L244 的 `RunContext(...)`：均追加

```python
            resolve_model=make_flow_model_resolver(agent.tenant_id if agent else flow_tenant_id),
            usage_sink=...,
```

具体取值：
- chat_entry：`agent.tenant_id`；usage_sink 用 `self.chat_usage_sink(model?)` 不可行（默认模型未必确定）——flow 默认模型由 `RunContext.model_config_id` 指定，且 llm_nodes 可能用节点覆盖模型，故 sink 无法预先绑定单一 model。**决策：flow 画布暂不注入 usage_sink（传 None，保持现状：画布调用不落 chat 用量行）**；模型解析回调必须注入。
- flows/service.py：`tenant_id` 为该 flow 所属租户（读取 `version`/`flow` 上下文）；若该文件构造时无 tenant_id 变量则从 `self`/`ctx` 取，须先读该函数确认变量名再填。

两文件顶部 import：`from app.tenant.flows.services.run_context import make_flow_model_resolver`（chat_rag.py 属 agents 域 import flows 域服务——同属 L1，agents 已依赖 flows 域，可接受）。

- [ ] **Step 5: 运行 flow 相关测试**

Run: `cd backend && .venv/bin/python -m pytest tests/flow -q`
Expected: PASS（`test_flow_multimodal.py` patch `llm_nodes.resolve_model_for_invoke` 的用例需同步改 patch 目标为 `make_flow_model_resolver` 或注入 fake `ctx.resolve_model`——**修改该测试**：删除对 `resolve_model_for_invoke` 的 monkeypatch，改为构造带 `resolve_model=async fake` 的 RunContext）

- [ ] **Step 6: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/llm_nodes.py backend/app/tenant/flows/services/run_context.py backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py backend/tests/flow/test_flow_multimodal.py
git commit -m "refactor(flow): 画布 LLM 节点改由运行上下文注入模型解析回调"
```

---

### Task 9: 迁移 deepagents 编排链（orchestrator）

**Files:**
- Modify: `backend/app/integrations/deepagents/orchestrator.py`
- Test: `backend/tests/tenant/agents/test_deepagents_orchestrator.py`（仅私有函数，不受影响）+ 全量回归

**Interfaces:**
- Consumes: Task 3 门面（经注入的 `svc` 鸭子调用）
- Produces: 无新接口

- [ ] **Step 1: 改写 `_platform_plan` 与 `_run_platform_planned`**

`_platform_plan` 签名由 `(*, db=None, tenant_id=None)` 改为 `(*, svc: AgentService)`（`run_subagent_planned_chat` 始终有 svc）；内部两处 `ainvoke_chat`：

L94 规划调用原：

```python
    raw = await ainvoke_chat(
        parent.model_config,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        db=db,
        tenant_id=tenant_id,
        source_id=parent.id,
    )
```

改为：

```python
    model = await svc.resolve_invoke_model(parent.model_config)
    usage_sink = svc.chat_usage_sink(model, source_id=parent.id)
    raw = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        usage_sink=usage_sink,
    )
```

`_run_platform_planned` 内 L123 调用 `_platform_plan(parent, bindings, body.query, db=svc.db, tenant_id=svc.ctx.tenant_id)` → `_platform_plan(parent, bindings, body.query, svc=svc)`；合成调用 L178 同 pattern 改为 resolve + sink + 去 db/tenant/source_id。
（若 `parent.model_config` 为 None 的分支已在 `_platform_plan` 开头守卫，合成分支 L177 也已有 `if parent.model_config:` 守卫。）

- [ ] **Step 2: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿

- [ ] **Step 3: Commit**

```bash
git add backend/app/integrations/deepagents/orchestrator.py
git commit -m "refactor(agents): deepagents 编排经 AgentService 门面解析模型与用量"
```

---

### Task 10: 收尾验证与文档同步

**Files:**
- Modify: `docs/architecture/layering.md`（§2.2 例外/修订记录）
- Modify: `backend/README.md`（如需）

**Interfaces:**
- Consumes: 全部任务产物

- [ ] **Step 1: 全量回归 + 体量自检 + ruff**

Run:
```bash
cd backend && .venv/bin/python -m pytest -q
```
Expected: 全绿（430 基线 ± 新增测试）。

Run: `cd backend && find app -name '*.py' -exec wc -l {} + | awk '$1 >= 500'`
Expected: 无 ≥500 行文件（自检不通过需拆分再提交）。

Run: `cd backend && .venv/bin/ruff check app/tenant/agents/services/agent/chat_rag.py app/tenant/models/services/usage.py app/integrations/langchain/chat_models.py app/integrations/langchain/tool_agent/loop.py app/integrations/langgraph/runner.py app/integrations/langgraph/graphs/rag_qa.py app/integrations/deepagents/orchestrator.py app/flow_runtime/nodes/llm_nodes.py app/tenant/flows/services/run_context.py`
Expected: All checks passed!

- [ ] **Step 2: 残留 import 审计**

Run: `cd backend && rg -n "app\.tenant\.models\.services" app/integrations app/flow_runtime`
Expected: 仅剩允许项——即 `integrations/litellm/adapter.py` 若仍由 L1 usage 反向 import 属合规（L1→L3）；正向残留（L3→L1）应为空。若 `runner.py` 等仍引用 `agents.constants` 常量，记录为遗留常量引用（常量 import 不属服务层越界，可在本任务内一并下沉 `integrations/agents_constants` 或注明后续 B-2 处理，二选一并写进 commit message）。

- [ ] **Step 3: 更新 layering.md**

`docs/architecture/layering.md`：
1. §2.2 下方 §2.3 之前或修订记录处，若本计划推进前在"过渡期例外"列过 `tenant.models.services.*` 相关条目，移除已收敛项并注明"2026-09-08 收敛对话/画布调用链（见 plan `2026-09-08-engine-di-chat-invoke-chain`）"。
2. 修订记录表追加行：`| 2026-09-08 | B-1：ainvoke_chat/runner/rag_qa/tool_agent/deepagents/llm_nodes 模型解析与用量 sink 注入，收敛 integrations/flow_runtime → tenant.models.services 反依赖 |`

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/layering.md backend/README.md
git commit -m "docs: 记录对话链模型解析与用量记录依赖反转（B-1）"
```

---

## Self-Review

**1. Spec coverage（针对 B-1 目标）**
- `chat_models.ainvoke_chat` 反依赖 → Task 4 ✅
- `litellm/adapter` 反依赖 → Task 1 ✅
- `tool_agent/loop` 的 model_resolve/usage 反依赖 → Task 6 ✅
- `langgraph/runner` 的 resolve 反依赖 → Task 7 ✅
- `rag_qa` generate/fallback 的 db/tenant 透传 → Task 7 ✅
- `rag_answer`（rag/generate）→ Task 7 ✅
- `deepagents/orchestrator` 的 ainvoke_chat(db=...) → Task 9 ✅
- `flow_runtime/nodes/llm_nodes` resolve 反依赖 → Task 8 ✅
- **明确不在本计划（B-2 延展）**：`embeddings.py`/`vectorstores.py`/`visual_embeddings.py` 的 embedding/rerank/search_log 注入；`generative/{persist,reference,compliance,jobs}`、`chat/multimodal.py`、`langchain/tools.py`、`tool_agent/artifacts.py` 的行为反依赖；flow_runtime 的 image/video/media/tool/compliance 节点与 subflow；deepagents 的 `agents.schemas/constants` 类型 import（常量/schema 依赖是否迁移至中立契约，单独评审）。

**2. Placeholder scan**
- 迁移点均给出 old → new 代码；两处需要执行者先读文件确认局部变量（`flows/service.py` 构造处的 tenant_id 变量名、`rag_qa` 节点内 `db` 是否仍被媒体解析使用）在 Step 内以"先读确认再填/勿删"指令给出，属有意的精确性提示而非 TBD。

**3. Type consistency**
- `UsageSink` 协议：Task 1 定义（仅 `record`），Task 2 `ChatUsageSink` 实现，Task 4-9 均按 `usage_sink: UsageSink | None` 传参；adapter 参数名统一 `usage_sink`。
- `resolve_invoke_model(model: ModelConfig | None) -> ModelConfig`、`chat_usage_sink(model, *, source_id) -> ChatUsageSink` 由 Task 3 定义，Task 5/6/7/9 一致引用。
- `RunContext.resolve_model: Callable[[str], Awaitable[ModelConfig]] | None` 由 Task 8 定义并被 `llm_nodes` 以 `str(model_id)` 调用、helper 返回同签名。✅
