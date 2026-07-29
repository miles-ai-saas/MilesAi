# 对话 WebSocket 真 token 流式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 直连 LLM 与 RAG 最终生成经 LiteLLM `stream=True` 推送真 `chat.delta`；tool 路径仍切块兜底；HTTP 整包不变。

**Architecture:** 可选 `on_delta` 回调自 LiteLLM → `ainvoke_chat` → `rag_answer` / LangGraph generate·fallback → `AgentService.chat` → WS。有真流式时跳过 `emit_answer_deltas`。协议与前端默认不改（`applyChatResponse` 已用 `chat.done.answer` 覆盖气泡）。

**Tech Stack:** LiteLLM `acompletion(stream=True)`、FastAPI WebSocket、现有 agents chat Mixin。

**Spec:** [docs/superpowers/specs/2026-07-29-agent-chat-true-streaming-design.md](../specs/2026-07-29-agent-chat-true-streaming-design.md)

## Global Constraints

- MVP 范围 **B**：直连 + 线性 RAG + LangGraph `generate`/`fallback` 真流式。
- tool_agent / pending_tool / flow / A2A：**不**真流式；可继续 `emit_answer_deltas`。
- WS 信封不变：`chat.delta` payload `{ "text": "..." }`。
- HTTP `POST /chat` 不传 `on_delta`，行为不变。
- 中间节点（grade/rewrite）**不**传 `on_delta`。
- 合规改写后以 `chat.done.answer` 为准；前端已有 done 覆盖。
- Commit message 简体中文 Conventional Commits。
- 单文件仍遵守 &lt;500 行；新增逻辑优先进现有模块，勿胀爆。

---

## File Structure

| 路径 | 职责 |
|------|------|
| `backend/app/integrations/litellm/adapter.py` | 新增 `litellm_chat_completion_stream` |
| `backend/app/integrations/langchain/chat_models.py` | `ainvoke_chat(..., on_delta=)` |
| `backend/app/rag/generate/answer.py` | `rag_answer(..., on_delta=)` 透传 |
| `backend/app/integrations/langgraph/runner.py` | `run_rag_workflow(..., on_delta=)` → configurable |
| `backend/app/integrations/langgraph/graphs/rag_qa.py` | generate/fallback 读 configurable 传 ainvoke |
| `backend/app/tenant/agents/services/agent/chat_rag.py` | direct_chat / rag_chat 透传 on_delta |
| `backend/app/tenant/agents/services/agent/chat_entry.py` | `chat(..., on_delta=)` 透传 |
| `backend/app/tenant/agents/ws/chat.py` | 注入 on_delta；跳过已流式切块 |
| `backend/app/tenant/agents/ws/protocol.py` | 可保留 `emit_answer_deltas` 作兜底 |
| `backend/tests/infra/` 或 `tests/tenant/agents/` | stream unit + 透传测 |
| `docs/features/agent-chat-websocket.md` 等 | 文档状态更新 |

---

### Task 1: LiteLLM stream + ainvoke_chat

**Files:**
- Modify: `backend/app/integrations/litellm/adapter.py`
- Modify: `backend/app/integrations/langchain/chat_models.py`
- Create: `backend/tests/infra/test_litellm_chat_stream.py`（若无 `tests/infra` 则用 `tests/tenant/agents/test_chat_stream.py`）

**Interfaces:**
- Produces:

```python
from collections.abc import Awaitable, Callable

OnDelta = Callable[[str], Awaitable[None]]

async def litellm_chat_completion_stream(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = HTTP_DEFAULT_TIMEOUT_SEC,
    usage_ctx: Any | None = None,
    on_delta: OnDelta | None = None,
) -> str: ...

async def ainvoke_chat(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    db: Any | None = None,
    tenant_id: Any | None = None,
    source_id: UUID | None = None,
    on_delta: OnDelta | None = None,
) -> str: ...
```

- [ ] **Step 1: 写失败测试（mock stream）**

```python
# tests/infra/test_litellm_chat_stream.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_litellm_chat_completion_stream_calls_on_delta_and_returns_full():
    from app.integrations.litellm.adapter import litellm_chat_completion_stream
    from app.models.model import ModelConfig  # 或用 MagicMock 满足所需字段

    chunks = []
    async def on_delta(t: str):
        chunks.append(t)

    # Fake async iterator yielding objects with choices[0].delta.content
    class Delta:
        def __init__(self, content):
            self.content = content
    class Choice:
        def __init__(self, content):
            self.delta = Delta(content)
    class Chunk:
        def __init__(self, content, usage=None):
            self.choices = [Choice(content)] if content is not None else []
            self.usage = usage

    async def fake_stream(**kwargs):
        assert kwargs.get("stream") is True
        async def gen():
            yield Chunk("你")
            yield Chunk("好")
            yield Chunk(None, usage=MagicMock(prompt_tokens=1, completion_tokens=2, total_tokens=3))
        return gen()

    model = MagicMock()
    model.model_type = "llm"
    model.api_key_encrypted = "k"
    model.extra = {}
    # 按 adapter 实际读取的字段补齐；必要时 patch resolve_litellm_model / _ensure_*

    with patch("app.integrations.litellm.adapter._import_litellm") as imp, \
         patch("app.integrations.litellm.adapter.resolve_litellm_model", return_value="openai/gpt-test"), \
         patch("app.integrations.litellm.adapter._ensure_messages_valid_for_chat"), \
         patch("app.integrations.litellm.adapter._resolve_api_base", return_value=None):
        litellm = MagicMock()
        litellm.acompletion = AsyncMock(side_effect=fake_stream)
        imp.return_value = litellm
        text = await litellm_chat_completion_stream(
            model, [{"role": "user", "content": "hi"}], on_delta=on_delta
        )
    assert text == "你好"
    assert chunks == ["你", "好"]
```

实现时按真实 `ModelConfig` / helper 签名微调 mock（测试必须红→绿）。

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/infra/test_litellm_chat_stream.py -q
```

Expected: FAIL（函数未定义或 ImportError）

- [ ] **Step 3: 实现 `litellm_chat_completion_stream`**

要点：
- `kwargs["stream"] = True`
- `response = await litellm.acompletion(**kwargs)` 后 `async for chunk in response`
- 提取 `choices[0].delta.content`；非空则 `await on_delta(piece)` 并拼进 `parts`
- 若 chunk 带 usage，结束时 `record_model_usage`（与非流式一致）
- 返回 `"".join(parts)`；空结果按现网策略抛 `AppError` 或返回 `""`（与非流式对齐）

- [ ] **Step 4: `ainvoke_chat` 分支**

```python
    if on_delta is not None:
        return await litellm_chat_completion_stream(
            model, openai_msgs,
            temperature=temperature, max_tokens=max_tokens,
            usage_ctx=usage_ctx, on_delta=on_delta,
        )
    return await litellm_chat_completion(...)
```

补测：`on_delta=None` 时仍调用非流式（可 mock 断言）。

- [ ] **Step 5: 跑测通过并 commit**

```bash
cd backend && python -m pytest tests/infra/test_litellm_chat_stream.py -q
```

```bash
git add backend/app/integrations/litellm/adapter.py \
  backend/app/integrations/langchain/chat_models.py \
  backend/tests/infra/test_litellm_chat_stream.py
git commit -m "$(cat <<'EOF'
feat(integrations): 增加 LiteLLM 对话真流式与 ainvoke on_delta

供直连/RAG WebSocket 推送 chat.delta。
EOF
)"
```

---

### Task 2: rag_answer + LangGraph 透传 on_delta

**Files:**
- Modify: `backend/app/rag/generate/answer.py`
- Modify: `backend/app/integrations/langgraph/runner.py`
- Modify: `backend/app/integrations/langgraph/graphs/rag_qa.py`
- Test: 扩展 `test_litellm_chat_stream.py` 或新建 `tests/rag/test_rag_answer_stream.py`（mock `ainvoke_chat`）

**Interfaces:**
- Consumes: `ainvoke_chat(..., on_delta=)`
- Produces:

```python
async def rag_answer(..., on_delta: OnDelta | None = None) -> tuple[str, list[dict]]:
async def run_rag_workflow(..., on_delta: OnDelta | None = None) -> tuple[str, list, list]:
# run_config["configurable"]["on_delta"] = on_delta
# generate/fallback: on_delta = config["configurable"].get("on_delta")
```

- [ ] **Step 1: 失败测试 — rag_answer 透传**

```python
@pytest.mark.asyncio
async def test_rag_answer_forwards_on_delta(monkeypatch):
    seen = {}
    async def fake_ainvoke(*args, **kwargs):
        seen["on_delta"] = kwargs.get("on_delta")
        return "ans"
    # patch retrieve_hits 返回 []，patch ainvoke_chat
    ...
    async def delta(_): ...
    await rag_answer(..., on_delta=delta)
    assert seen["on_delta"] is delta
```

- [ ] **Step 2: 实现 rag_answer / runner / generate / fallback 透传**

- grade / retry 路径的 `ainvoke_chat`：**不要**传 `on_delta`
- `run_config["configurable"]["on_delta"] = on_delta`

- [ ] **Step 3: pytest 通过并 commit**

```bash
git commit -m "$(cat <<'EOF'
feat(rag): RAG 与 LangGraph 最终生成透传 on_delta

检索与评分节点不推送用户 delta。
EOF
)"
```

---

### Task 3: AgentService + WS 接线

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_entry.py` — `chat(self, agent_id, body, *, on_delta=None)`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py` — `direct_chat` / `rag_chat` 透传；`chat_as_child` 可选不传（子 Agent 若走 WS 再定；MVP 子路径可不流）
- Modify: `backend/app/tenant/agents/ws/chat.py` — `_run_chat_turn`

**Interfaces:**
- Produces: WS 侧

```python
streamed = False
async def on_delta(text: str) -> None:
    nonlocal streamed
    if text:
        streamed = True
        await proto.send_json(ws, proto.CHAT_DELTA, {"text": text})

response = await AgentService(db, ctx).chat(agent_id, body, on_delta=on_delta)
# steps / pending_tool 处理同现网
if not streamed:
    await proto.emit_answer_deltas(ws, response.answer)
else:
    # 若合规后 answer 与已推送不一致：仍发 chat.done，由前端 applyChatResponse 覆盖
    pass
await proto.send_json(ws, proto.CHAT_DONE, response.model_dump(mode="json"))
```

- [ ] **Step 1: 单元测 — 已 stream 则不切块**

可用 AsyncMock WebSocket + patch `AgentService.chat`：
- chat 内调用传入的 `on_delta("a")` 再返回 `ChatResponse(answer="a")`
- 断言 `send_json` 含 `chat.delta`，且 **未** 因切块再发多余 delta（或断言 `emit_answer_deltas` 未被调用）

- [ ] **Step 2: 实现 chat / direct_chat / rag_chat / WS**

注意：`rag_chat` 调 `run_rag_workflow` / `rag_answer` / `ainvoke_chat`（direct）时传入 `on_delta`；走 `run_tool_calling_chat` 时 **不传**。

- [ ] **Step 3: 跑 `tests/tenant/agents` + stream 测**

```bash
cd backend && python -m pytest tests/tenant/agents tests/infra/test_litellm_chat_stream.py -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): WebSocket 直连/RAG 路径接入真 token 流式

已推送 delta 时跳过整段切块；tool 路径保持兜底。
EOF
)"
```

---

### Task 4: 文档与前端确认

**Files:**
- Modify: `docs/features/agent-chat-websocket.md` — 状态改为部分真流式；§1.2 / delta 说明
- Modify: `docs/architecture/realtime-transport-design.md` — R2 状态
- Modify（仅必要时）: `ui/workbench/features/agents/hooks/use-agents-chat-messaging.tsx`

- [ ] **Step 1: 确认前端**

`applyChatResponse(res, ...)` 已用 `res.answer` 写气泡 → **默认无代码改动**。若发现 done 后仍显示旧 streamText，补一行以 `res.answer` 覆盖（在现有 `applyChatResponse` 内）。

- [ ] **Step 2: 更新两处文档**（去掉「仅模拟」绝对表述；标明 tool 仍切块）

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(agents): 更新对话真流式 As-Is 说明

直连与 RAG 最终生成已接 LiteLLM stream。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| litellm stream + usage | 1 |
| ainvoke on_delta | 1 |
| rag_answer / LangGraph generate·fallback | 2 |
| grade 不传 delta | 2 |
| Agent chat + WS 跳过切块 | 3 |
| tool 仍切块 | 3 |
| 文档 / 前端 done 覆盖 | 4 |
| HTTP 不变 | 1–3（不传 on_delta） |

## Placeholder scan

无 TBD；mock 细节允许按 `ModelConfig` 真实字段微调，但断言行为固定。
