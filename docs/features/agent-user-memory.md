# 跨会话用户记忆（长期记忆）

> 类型：功能说明 | 状态：已实现（MVP） | 代码：`agt_user_agent_memories` / `UserMemoryService`

## 能力

- 粒度：`(tenant_id, user_id, agent_id, kind)`，`kind` ∈ `summary` | `preference`
- **读**：直连 / tool_agent / RAG 的 system 注入「关于该用户的长期记忆」块（默认关闭）
- **写**：对话成功后 Celery `run_user_memory_extract`，任务携带本轮快照（避免 commit 竞态）
- **管理**：`GET/DELETE /agents/{id}/user-memories`（当前用户）；表单开关 `config.user_memory.enabled`

## 配置

```json
{ "user_memory": { "enabled": true, "max_inject_chars": 2000 } }
```

## 非目标（本批）

- 向量召回、写入 KB、Flow / A2A / subagent 主路径
- 同步 chat 路径抽取、跨 Agent 全局画像、Admin 运营台
