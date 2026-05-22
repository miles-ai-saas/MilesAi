# 自定义智能体引用外部 A2A

> 关联：[a2a-protocol-integration.md](./a2a-protocol-integration.md)、[internal-agent-orchestration.md](./internal-agent-orchestration.md)

## 数据

- `agt_agent_a2a_peer_refs`：`agent_id` + `peer_id`，`trigger_keywords`（JSON 数组），`role_hint`，`enabled`
- 与 `agt_sub_agent_bindings` **分表**，语义不同

## 对话策略（默认 `rules_then_plan`）

1. 先执行本智能体能力（RAG / 流程 / 内部协同）
2. **规则层**：用户问题包含某 peer 的 `trigger_keywords` → 强制调用该外部 Agent
3. **规划层**：未命中或策略为 `plan_only` 时，主模型输出 `a2a_steps` 选择 peer
4. 调用 `invoke_a2a_peer`（JSON-RPC `message/send` 或 Card 占位）
5. 主模型综合「本智能体回答 + 外部结果」

## 配置

| 字段 | 说明 |
|------|------|
| `a2a_invoke_policy` | `rules_then_plan` / `rules_only` / `plan_only` |
| `max_a2a_calls_per_turn` | 默认 2 |

## 前置条件

外部 peer 须在 A2A Tab **同步 Card** 且状态为 `active` 方可绑定。
