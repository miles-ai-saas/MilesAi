# 智能体钩子（Hook）

**日期：** 2026-05-27  
**状态：** HTTP 钩子已实现；Python 钩子未实现  
**PRD 对照：** 模块2 全局执行钩子  
**架构：** [technical-design.md §11.2](../architecture/technical-design.md#112-钩子) · [hooks.md](../guides/hooks.md)

---

## 1. 背景与目标

**钩子**是智能体/流程/工具执行链上的 **切面扩展点**：租户配置 HTTP Webhook，在关键节点接收 Event v1 信封，实现审计、计费、IAM、请求 enrich 等。

与 **合规敏感词** 分工：合规为平台强约束扫描；钩子默认旁路，可配置 `on_failure: fail_request` 阻断。

```text
BEFORE_CALL → 合规 check_input → … 推理/工具/流程 …
→ 合规 check_output → AFTER_CALL
异常 → ON_ERROR → re-raise
```

### 1.1 交付范围

- 钩子定义 CRUD、绑定 CRUD、执行日志查询
- HTTP 执行：Event v1、`block` / `modify` 响应
- 挂载：Agent chat、Flow run、Tool invoke
- triggers：before/after_call、before/after_reasoning、before/after_tool、on_error
- 前端：`/workbench/hooks`

### 1.2 明确不做

- Python 钩子（`python_not_implemented` 跳过）
- 画布内每个 LLM 节点独立 reasoning 钩子
- `scope=tool` 绑定（执行点未接）

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `hook_definitions` | name、hook_type、config（url/method/headers/on_failure） |
| `hook_bindings` | hook_id、scope、target_id、trigger、priority |
| `hook_execution_logs` | 每次执行结果、耗时、HTTP 状态 |

### 2.1 hook_type

| 值 | 状态 |
|----|------|
| `http` | ✅ |
| `python` | ❌ 未实现 |

### 2.2 trigger

| 值 | Agent chat | Flow run | Tool invoke |
|----|:----------:|:--------:|:-----------:|
| `before_call` / `after_call` | ✅ | ✅ | — |
| `before_reasoning` / `after_reasoning` | ✅* | ❌ | — |
| `before_tool` / `after_tool` | ✅ | ❌ | ✅ |
| `on_error` | ✅ | ✅ | — |

\* 仅直连 LLM / RAG 路径；不含 A2A 宿主、画布 flow、tool_agent 内每轮 LLM。

### 2.3 scope

`global` | `agent` | `flow` | `tool`（未接）| `app`（预留）

---

## 3. API

前缀：`/api/v1/hooks`  
权限：`hook:read` · `hook:write`

```
GET  /hooks/meta
GET  /hooks
POST /hooks
PATCH/DELETE /hooks/{id}
GET  /hooks/{id}/bindings
POST /hooks/{id}/bindings
DELETE /hooks/bindings/{binding_id}
GET  /hooks/executions?page=
```

---

## 4. HTTP 契约（Event v1）

请求体 envelope：

```json
{
  "event": "hook.before_call",
  "version": "1",
  "tenant_id": "uuid",
  "timestamp": "ISO8601",
  "payload": { "module": "agent_chat", "agent_id": "…", "query": "…" }
}
```

响应（可选）：

| action | 效果 |
|--------|------|
| `continue` | 默认，继续 |
| `block` | 中断请求，返回错误 |
| `modify` | 改写 query/text（按 payload 字段） |

`config.on_failure`：`ignore`（默认）| `fail_request`。

详见 [hooks.md §5–§6](../guides/hooks.md)。

---

## 5. 运行时入口

```
HookRunner.run(trigger, scope, target_id, payload)
    → HookExecutor 按 priority 串行
    → HttpHookExecutor POST config.url
    → 写 hook_execution_logs
```

调用方：

- `AgentService.chat` / `chat_as_child`（部分 trigger）
- `FlowService.run`
- `invoke_tool_with_context`

---

## 6. 前端

```
ui/workbench/app/workbench/hooks/page.tsx
```

`GET /hooks/meta` — trigger/scope 枚举文案。

---

## 7. 后端文件清单

```
backend/app/tenant/hooks/models.py
backend/app/tenant/hooks/views/hooks.py
backend/app/tenant/hooks/services/hook_runner.py
backend/app/tenant/hooks/services/hook_executor.py
backend/app/tenant/agents/services/agent/
backend/app/tenant/flows/services/flow.py
backend/app/tenant/tools/invoke/
```

---

## 8. 测试计划

1. 创建 HTTP hook + global before_call → chat 后 executions 有记录
2. 响应 block → chat 4xx
3. on_failure=fail_request + Webhook 500 → 主请求失败
4. agent scope binding 仅命中对应 agent_id
5. before_tool → invoke 工具前后各一条 log

---

## 9. 参考

- [hooks.md](../guides/hooks.md) — 完整契约与对照表
- [compliance.md](./compliance.md) — 敏感词（并行能力）
- [hooks.md §9](../guides/hooks.md) — 全站 `/meta` 约定
