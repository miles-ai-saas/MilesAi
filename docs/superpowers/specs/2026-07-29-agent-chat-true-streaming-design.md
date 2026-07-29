# 设计：对话 WebSocket LLM 真 token 流式（MVP B）

**日期：** 2026-07-29  
**状态：** 已批准（对话确认；待实现）  
**对照：** [agent-chat-websocket.md](../../features/agent-chat-websocket.md) · [realtime-transport-design.md](../../architecture/realtime-transport-design.md)  
**动机：** v1 `chat.delta` 为整段 answer 切块模拟；工作台直连/RAG 问答需真正边生成边推送。

---

## 1. 目标与非目标

### 目标

1. **直连 LLM**（`direct_chat`）与 **RAG 最终生成**（线性 `rag_answer`、LangGraph `generate` / `fallback`）经 LiteLLM `stream=True` 产出真 token，经现有 WS 帧 `chat.delta` 推送。
2. **协议与前端不变**：`payload.text`、`onDelta`、`chat.done` 字段保持兼容；`chat.done.answer` 等于累计 delta（及合规/Hook 后的最终文本，见 §4.3）。
3. **HTTP `POST /chat` 行为不变**：整包返回；不强制消费流式回调。
4. **tool_agent / 工具确认 / 生图生视频路径**：本 MVP **不**接真流式；仍可走现有「整段后 `emit_answer_deltas`」兜底。

### 非目标

- tool_agent 多轮 function calling 内的 token 流
- 对外 OpenAPI / 第三方 HTTP SSE 流式
- 全站统一 WS 网关、断线续传 v2
- 改前端协议或强制去掉 HTTP 降级

---

## 2. 方案选择

| 方案 | 结论 |
|------|------|
| 1. 可选 `on_delta` 回调贯穿 LiteLLM → ainvoke → RAG/LangGraph → WS | **采用** |
| 2. WS 在 chat 完成后二次 stream | 拒绝（双倍计费/延迟） |
| 3. 整条 chat 改为 async generator | 拒绝（改动面过大） |

**MVP 路径范围：B** — 直连 + RAG 最终生成；工具轮仍整段。

---

## 3. 架构

```text
Workbench WS chat.send
       │
       ▼
AgentService.chat(..., on_delta?)
       │
       ├─ A2A / subagent / flow / tool_agent / pending_tool
       │     → 整段 ChatResponse →（可选）emit_answer_deltas 切块
       │
       └─ direct_chat / rag_answer / LangGraph generate|fallback
             → litellm stream → on_delta(chunk) → chat.delta
             → 汇总 answer → 合规/Hook → chat.done
```

前端已有 `AgentChatWsClient` + `onDelta`，**无需协议变更**。

---

## 4. 接口设计

### 4.1 LiteLLM

在 `app/integrations/litellm/adapter.py`：

- 新增流式能力（推荐独立函数，避免破坏现有 `litellm_chat_completion` 签名语义），例如：

```python
async def litellm_chat_completion_stream(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = ...,
    usage_ctx: Any | None = None,
    on_delta: Callable[[str], Awaitable[None]] | None = None,
) -> str:
    """stream=True；对每个 content 增量 await on_delta；返回完整字符串；结束时记 usage。"""
```

- 从 LiteLLM stream chunk 提取 `delta.content`（兼容 str / 多模态退化）。
- usage：优先用流结束 usage chunk；无则按现网策略尽力记录（不得因缺 usage 失败整轮）。

### 4.2 `ainvoke_chat`

`app/integrations/langchain/chat_models.py`：

```python
async def ainvoke_chat(
    ...,
    on_delta: Callable[[str], Awaitable[None]] | None = None,
) -> str:
```

- `on_delta is None` → 现有非流式 `litellm_chat_completion`
- 有 `on_delta` → `litellm_chat_completion_stream`

### 4.3 RAG / LangGraph

- `rag.generate.rag_answer`：最终 `ainvoke_chat` 透传 `on_delta`
- LangGraph `generate` / `fallback`：透传 `on_delta`（经 `RunnableConfig` configurable 或显式参数，选与现图一致的最少侵入方式）
- **检索 / grade / rewrite** 等中间 LLM 调用：**不**传 `on_delta`（避免把内部推理打到用户气泡）

### 4.4 Agent 对话与 WS

- `AgentService` / Mixin：为可流式路径支持可选 `on_delta`（或专用 `chat_with_delta` 内部方法）；**对外 HTTP view 不传**。
- WS handler（`ws/chat.py`）：
  - 构造 `on_delta`：`await send_json(ws, CHAT_DELTA, {"text": chunk})`
  - 若本轮已通过 `on_delta` 推送过文本：**跳过** `emit_answer_deltas`
  - 若本轮无真流式（tool / pending / flow 等）：保持现有 `emit_answer_deltas`
- **合规出站**：若 `check_output` 改写/拦截 answer，则：
  - **优先策略（MVP）：** 流式过程推送的是模型原文；`chat.done.answer` 为合规后最终文本；若二者不一致，前端以 `chat.done` 为准刷新气泡（工作台已有 done 合并逻辑则复用；若无则补「done 覆盖」）。
  - 不在本 MVP 做「先缓冲再流式」的强合规（延迟体验差）。

### 4.5 协议

不变。文档更新：

- `docs/features/agent-chat-websocket.md`：标明直连/RAG 为真流式；tool 路径仍模拟切块
- `docs/architecture/realtime-transport-design.md`：状态栏更新 R2

---

## 5. 前端

- **默认不改**协议客户端。
- 验收时确认：流式过程中气泡递增；`chat.done` 后内容与最终 answer / artifacts / pending_tool 一致。
- 仅当 done 覆盖逻辑缺失时，做最小补丁。

---

## 6. 测试

| 用例 | 说明 |
|------|------|
| unit：stream adapter | mock LiteLLM async 迭代，断言 `on_delta` 调用序列与返回全文 |
| unit：ainvoke 分支 | `on_delta=None` 走非流；有回调走 stream |
| WS / agents（现有） | 不回归；必要时 mock chat 带 delta |
| 手工 | 工作台直连与带 KB RAG，观察网络帧间隔 |

---

## 7. 验收标准

- [ ] 直连 / 线性 RAG / LangGraph generate：`chat.delta` 在模型生成过程中到达（非整段生成后再切）
- [ ] `chat.done.answer` 与业务最终文本一致；累计 delta 在无合规改写时与 answer 一致
- [ ] tool_agent / `pending_tool` / HTTP POST 行为与现网一致
- [ ] 相关 pytest 通过；中文 Conventional Commits

---

## 8. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 部分供应商 stream usage 不完整 | 记账尽力而为；不阻断回答 |
| 合规改写与已推 delta 不一致 | done 覆盖；文档说明 |
| LangGraph configurable 传参侵入 | 优先 config 透传；失败则仅线性 RAG + direct 先上，LangGraph 紧随 |

回滚：关闭流式（`on_delta` 不传）即回切块行为；或 feature flag（可选，非必须）。

---

## 9. 决策记录

- 范围 **B**；方案 **1**（`on_delta` 贯穿）。
- 不做 tool 真流式、不做二次 stream、不改 WS 信封。
