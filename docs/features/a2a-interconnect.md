# A2A 外部互联

**状态：** 部分实现（登记/引用/宿主 ✅；对外 Card 待做）  
**PRD 对照：** 模块4 A2A 互联智能体  
**协议：** [A2A Protocol v1.0](https://a2a-protocol.org/v1.0.0/specification/) · [a2a.md](../guides/a2a.md)

---

## 1. 背景与目标

**A2A（Agent-to-Agent）** 用于跨厂商、跨平台的智能体互联：登记外部 Agent Card，通过标准 JSON-RPC 调用外部 Agent。

与 **内部协同**（`agt_sub_agent_bindings`）分表、分 Tab、互不替代。

| 模式 | 数据 | 行为 |
|------|------|------|
| **外部登记** | `agt_a2a_peers` | 维护目录、同步 Card |
| **互联宿主** | `agent_type=a2a` + `agt_a2a_peer_bindings` | 对话以调用外部为主 |
| **平台内引用** | `agt_agent_a2a_peer_refs` | custom 本地推理后再增强调外部 |

### 1.1 交付范围

- Peer CRUD、probe、sync-card
- 宿主智能体创建/绑定、trigger_keywords
- custom 智能体 peer_refs + `a2a_invoke_policy`
- `run_a2a_host_chat` / `augment_response_with_a2a`
- 前端：A2A 互联 Tab（外部登记、互联宿主）

### 1.2 明确不做

- 本平台对外 `/.well-known/agent-card.json`
- A2A 专用审计/限流（复用通用能力）

---

## 2. 数据模型

### 2.1 表 `agt_a2a_peers`

| 字段 | 说明 |
|------|------|
| `agent_card_url` | Card 拉取地址 |
| `agent_card_json` | 缓存 Card |
| `base_url` | 调用基址 |
| `auth_config` | 认证 JSON |
| `status` | pending / active / error / inactive |

### 2.2 表 `agt_a2a_peer_bindings`

互联宿主 → Peer：`trigger_keywords`（逗号分隔关键词命中强制路由）。

### 2.3 表 `agt_agent_a2a_peer_refs`

custom 智能体 → Peer：`trigger_keywords`、`role_hint`。

**宿主约束：** 禁止 `sub_agents` / `kb_ids` / `published_flow_id` 作为主路径。

---

## 3. 运行时

### 3.1 互联宿主

```
POST /agents/{a2a_host_id}/chat
    → run_a2a_host_chat
    → 规则/规划选 Peer
    → invoke_a2a_peer (JSON-RPC message/send)
    → steps: type=a2a_peer
```

### 3.2 custom + peer_refs

```
本地 RAG / 内部协同 / 流程 先执行
    → augment_response_with_a2a
    → config.a2a_invoke_policy:
        rules_then_plan | plan_only | rules_only
    → max_a2a_calls_per_turn (默认 2)
```

Peer 须 `status=active` 且 Card 有效。

---

## 4. API

### 4.1 Peer `/api/v1/a2a/peers`

```
GET  /a2a/peers/meta
GET  /a2a/peers
POST /a2a/peers
POST /a2a/peers/probe              # 探测连通性
GET/PATCH/DELETE /a2a/peers/{id}
POST /a2a/peers/{id}/sync-card
```

### 4.2 智能体

```
GET  /agents?agent_type=a2a       # 互联宿主列表
POST /agents/{id}/chat            # 宿主或 custom 增强
```

创建宿主：`agent_type=a2a`，绑定 peers 在 agent body 或专用表单。

---

## 5. 前端

| 组件 | 功能 |
|------|------|
| `A2aAgentsTab` | A2A 互联 Tab 容器 |
| `A2aPeersPanel` | 外部登记列表 |
| `A2aHostFormDialog` | 互联宿主表单 |
| `AgentFormStepContent` | custom 引用外部 Peer（第 4 步） |

工作台：`/workbench/agents` → Tab「A2A 互联」。

---

## 6. 后端文件清单

```
backend/packages/miles-portal/src/miles_portal/tenant/a2a/models.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/views/peers.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/card_client.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/invoke.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/
```

---

## 7. 测试计划

1. probe + sync-card → status active
2. 创建 a2a 宿主 + binding → chat 调外部（mock Card）
3. custom + peer_refs + trigger_keywords 命中 → 强制 Peer
4. inactive peer → 跳过或报错

---

## 8. 参考

- [a2a.md](../guides/a2a.md)
- [platform-agents.md](./platform-agents.md) — 内部协同对比
- [README.md §概念速查](../README.md) — 三 Tab 语义
