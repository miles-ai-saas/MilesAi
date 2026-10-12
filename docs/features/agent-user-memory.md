# 跨会话用户记忆（长期记忆）

> 类型：功能说明 | 状态：已实现 | 代码：`agt_user_agent_memories` / `UserMemoryService`

## 能力

- 粒度：`(tenant_id, user_id, agent_id, kind)`，`kind` ∈ `summary` | `preference`
- **读**：直连 / tool_agent / RAG / Flow / A2A 宿主 / **subagent 编排** 的 system 注入「关于该用户的长期记忆」块（默认关闭；顺序：长期 → 近期短程）
- **写**：上述路由（含 subagent）对话成功后 Celery `run_user_memory_extract`；upsert 时 best-effort 写入 `content_embedding`
- **管理**：`GET/DELETE /agents/{id}/user-memories`（当前用户）；表单开关 `config.user_memory.*`

## 配置

```json
{
  "user_memory": {
    "enabled": true,
    "max_inject_chars": 2000,
    "scope": "per_agent",
    "recall_mode": "all"
  }
}
```

| 键 | 说明 |
|----|------|
| `scope` | `per_agent`（默认）仅本智能体；`tenant_user` 合并同租户用户在各智能体下的记忆（标签带来源智能体名） |
| `recall_mode` | `all` 全量按字符预算截断；`relevant` 按本轮 query 向量/关键词相关性排序后再截断 |

## 向量

- 列：`content_embedding`（JSONB float 数组）
- 抽取 upsert 时用租户默认 embedding 模型；失败不影响主路径
- `relevant` 无向量时回退关键词重叠分

## 非目标（后续）

- 写入独立 KB / 知识图谱、同步 chat 路径抽取、Admin 运营台画像
