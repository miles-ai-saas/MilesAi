# ModelConfig.extra 与 invoke_mode 对照

> 类型：实现对照 | 关联：[model-providers.md](./model-providers.md)、[knowledge-base.md](./knowledge-base.md)、`backend/README.md` 常量分家

`agt_model_configs.extra`（JSONB）存放**调用形态**与**能力参数**。键名以代码常量为准，勿在业务层写魔法字符串。

---

## 1. 代码入口（真源）

| 范围 | 路径 | 内容 |
|------|------|------|
| 跨类型共用键 | `backend/packages/miles-common/src/miles_common/constants/model_extra.py` | `EXTRA_INVOKE_MODE`（值 `"invoke_mode"`） |
| 向量化 | `backend/packages/miles-integrations/src/miles_integrations/embeddings/constants.py` | `INVOKE_MODE_*`、`EXTRA_EMBEDDING_*` |
| 重排序 | `backend/packages/miles-integrations/src/miles_integrations/rerank/constants.py` | `INVOKE_MODE_*`、`EXTRA_RERANK_*` |
| 解析默认值 | `integrations/embeddings/model_meta.py`、`integrations/rerank/model_meta.py` | 按 `vendor` 推断默认 `invoke_mode` |
| 创建校验 | `tenant/models/services/model.py` | embedding/rerank 创建时校验 `invoke_mode` 是否在 registry 内 |
| 种子数据 | `scripts/seed/model_catalog.py` | 内置目录 `extra` 使用上述常量 |

---

## 2. 共用 extra 键

| 键（常量） | JSON 字段名 | 适用 `model_type` | 说明 |
|------------|-------------|-------------------|------|
| `EXTRA_INVOKE_MODE` | `invoke_mode` | `embedding`、`rerank` | 选择 Provider 实现；取值见下表（embedding 与 rerank **取值集合不同**） |

---

## 3. 向量化（`model_type = embedding`）

### 3.1 `invoke_mode` 取值

| 常量 | 值 | Provider | 典型场景 |
|------|-----|----------|----------|
| `INVOKE_MODE_LOCAL` | `local` | `LocalEmbeddingProvider` | 私有化 BGE / Sentence-Transformers，无需 API Key |
| `INVOKE_MODE_OPENAI_COMPATIBLE` | `openai_compatible` | `OpenAICompatibleEmbeddingProvider` | DashScope 兼容端点、vLLM/TEI 等 OpenAI 形状网关 |
| `INVOKE_MODE_LITELLM` | `litellm` | `LiteLLMEmbeddingProvider` | 经 LiteLLM 统一多厂商 |

注册与分发：`integrations/embeddings/registry.py` → `known_invoke_modes()`。

### 3.2 其他 extra 键

| 常量 | JSON 字段名 | 必填 | 说明 |
|------|-------------|------|------|
| `EXTRA_EMBEDDING_DIMENSION` | `embedding_dimension` | 创建时建议必填 | 向量维度；创建 KB 时固化，之后不可改模型维度 |
| `EXTRA_EMBEDDING_BATCH_SIZE` | `embedding_batch_size` | 否 | 批量 embed 上限；通义兼容端点见 `DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX`（10） |

### 3.3 示例（内置种子）

```json
{
  "invoke_mode": "local",
  "embedding_dimension": 768
}
```

```json
{
  "invoke_mode": "openai_compatible",
  "embedding_dimension": 1024,
  "embedding_batch_size": 10
}
```

---

## 4. 重排序（`model_type = rerank`）

### 4.1 `invoke_mode` 取值

| 常量 | 值 | Provider | 典型场景 |
|------|-----|----------|----------|
| `INVOKE_MODE_DASHSCOPE` | `dashscope` | `DashScopeRerankProvider` | 阿里云原生 text-rerank |
| `INVOKE_MODE_OPENAI_COMPATIBLE` | `openai_compatible` | `OpenAICompatibleRerankProvider` | `POST …/reranks` 形状网关 |

注册：`integrations/rerank/registry.py` → `known_invoke_modes()`。

### 4.2 其他 extra 键

| 常量 | JSON 字段名 | 适用 | 说明 |
|------|-------------|------|------|
| `EXTRA_RERANK_INSTRUCT` | `rerank_instruct` | 可选 | 查询指令；缺省用 `DEFAULT_RERANK_INSTRUCT` |
| `EXTRA_RERANK_REQUEST_FORMAT` | `rerank_request_format` | DashScope | `flat`（`RERANK_REQUEST_FORMAT_FLAT`）或 `nested`（`RERANK_REQUEST_FORMAT_NESTED`） |

### 4.3 示例（内置种子）

```json
{
  "invoke_mode": "dashscope",
  "rerank_request_format": "flat"
}
```

---

## 5. LLM / 其他类型

对话类（`llm`、`reasoning`、`vision`）主要走 LiteLLM，常用 extra：

| JSON 字段 | 说明 |
|-----------|------|
| `litellm_model` | 覆盖完整 LiteLLM model 字符串（见 [model-providers.md](./model-providers.md) §2.4） |

embedding/rerank **不要**与 LLM 混用同一套 `invoke_mode` 枚举；创建模型时 `model.py` 按 `model_type` 分别校验。

---

## 6. HTTP 超时

集成层出站 HTTP 默认超时：`integrations/http_constants.HTTP_DEFAULT_TIMEOUT_SEC`（120s），用于 embedding/rerank OpenAI 兼容客户端与 LiteLLM adapter。

