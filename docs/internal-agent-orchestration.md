# 平台内智能体协同编排（内部多智能体）

> 版本：v1.0 | 日期：2026-05-21  
> 状态：**已落地**（DeepAgents + `agt_sub_agent_bindings`）  
> **注意：这不是 A2A 协议。** 外部互联见 [a2a-protocol-integration.md](./a2a-protocol-integration.md)。

---

## 1. 产品语义

| 概念 | 说明 |
|------|------|
| **自定义智能体** | `agent_type=custom`，单智能体能力单元（模型、KB、工具、流程） |
| **内部协同** | 同一租户下，主智能体通过 `agt_sub_agent_bindings` 绑定其他 **custom** 智能体，由 DeepAgents（或平台 JSON 规划）委派子任务 |
| **与 A2A 区别** | 子智能体是本平台 `agt_agents` 记录，不走 `/.well-known/agent-card.json`，不跨厂商 |

列表卡片展示示例：`内部协同 · 3 子智能体`（**不**显示为 A2A）。

---

## 2. 数据与配置

- 关联表：`agt_sub_agent_bindings`（`parent_agent_id`, `child_agent_id`, `role_hint`, `sort_order`）
- 主智能体 `Agent.config`（有绑定时自动写入）：
  - `runtime_mode=autonomous`
  - `planner=deepagents`
  - 可选：`subagent_parallel`, `force_platform_planner`, `max_plan_iterations`, `max_subagent_calls`

约束见 [deepagents-subagents.md](./deepagents-subagents.md)（同租户、禁止自绑、禁止成环、最多 8 个、子节点为叶子）。

---

## 3. 执行路径

`POST /agents/{id}/chat` → `run_subagent_planned_chat` → DeepAgents 或平台降级。

响应 `steps` 中 `type=subagent` 记录委派轨迹。

---

## 4. 前端配置入口

- **自定义智能体** 创建/编辑向导第 4 步：「知识库与内部协同」
- 仅 `agent_type=custom` 可配置子智能体绑定

---

## 5. 相关文档

- [deepagents-subagents.md](./deepagents-subagents.md)
- [agent-enhancement-langchain-stack.md](./agent-enhancement-langchain-stack.md)
