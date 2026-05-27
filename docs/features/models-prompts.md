# 模型供应商与提示词

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块3 AI模型与提示词中心  
**架构：** [model-providers.md](../guides/model-providers.md)

---

## 1. 背景与目标

**模型供应商** 管理对话/Embedding/Rerank 等模型端点（内置目录 + 租户自定义 BYOK）；**提示词模板** 供智能体、流程节点引用。

### 1.1 交付范围

- 模型：列表、创建自定义、PATCH、删除；内置模型租户凭证覆盖
- Embedding profiles 与 KB 创建绑定（见 [kb-ingest-retrieval.md](./kb-ingest-retrieval.md)）
- 提示词模板 CRUD、分类、标签
- 前端：`/workbench/models`、`/workbench/prompts`
- LiteLLM `acompletion` 统一对话调用

### 1.2 明确不做

- 模型自动故障转移集群
- 提示词 A/B 实验平台

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `agt_model_configs` | 模型端点、`api_key_encrypted`、provider、capabilities |
| `agt_model_tenant_credentials` | 租户覆盖内置模型 AK |
| `prm_prompt_templates` | 提示词模板 |

内置模型：`tenant_id` 为空，全平台可见；租户自定义行带 `tenant_id`。

---

## 3. API

### 3.1 模型 `/api/v1/models`

权限：`model:read` · `model:write`

```
GET  /models/meta
GET  /models                    # 内置 + 本租户自定义合并列表
POST /models
PATCH /models/{id}
DELETE /models/{id}
PUT  /models/builtin/{id}/credentials
DELETE /models/builtin/{id}/credentials
```

### 3.2 提示词 `/api/v1/prompt-templates`

权限：`prompt:read` · `prompt:write`

```
GET  /prompt-templates/meta
GET  /prompt-templates?category_id=&tag_ids=
POST /prompt-templates
PATCH /prompt-templates/{id}
DELETE /prompt-templates/{id}
```

### 3.3 KB 相关

```
GET /kb/embedding-profiles      # 创建 KB 时选 embedding_profile
```

---

## 4. 运行时

- 对话：`integrations/litellm` → `acompletion`
- 向量：`integrations/langchain/embeddings` → `get_embeddings_for_kb(kb)`
- Rerank：KB 级 `rerank_model_config_id`（可选）

API Key **加密存库**，非环境变量（部署级默认 embedding 除外）。

---

## 5. 前端

```
ui/workbench/app/workbench/models/page.tsx
ui/workbench/app/workbench/prompts/page.tsx
```

---

## 6. 后端文件清单

```
backend/app/models/model.py
backend/app/models/model_tenant_credential.py
backend/app/tenant/models/
backend/app/tenant/prompts/
backend/app/integrations/litellm/
backend/app/integrations/embedding_profiles.py
```

---

## 7. 测试计划

1. 创建自定义模型 + AK → agent 绑定 → chat 成功
2. 内置模型 PUT credentials → 租户隔离
3. 提示词模板 + category/tag 筛选
4. KB 创建后改 embedding_dimension → 拒绝

---

## 8. 参考

- [model-providers.md](../guides/model-providers.md)
- [ai-stack.md](../guides/ai-stack.md)
- [model-config-extra.md](../guides/model-config-extra.md)
