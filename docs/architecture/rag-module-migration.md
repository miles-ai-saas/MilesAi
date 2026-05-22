# RAG 模块迁移清单

> 依据：[layering.md](./layering.md)  
> 状态：**迁移完成**（2026-05-22）

## 终态结构

```
app/rag/              # L2 RAG 能力
app/integrations/     # L3 LangChain / LangGraph / LiteLLM / DeepAgents
app/infra/vector_store/  # L4 向量客户端（factory + 三后端）
app/tenant/kb/        # L1 用例（ingest 状态机、配额、API）
```

已删除：`app/ai`、`app/ai_stack`。

---

## 阶段摘要

| 阶段 | 内容 | 状态 |
|------|------|------|
| 0 | 文档 `layering.md`、迁移清单 | [x] |
| 1 | 建立 `app/rag/`，迁 parse/chunk/index/retrieve/generate | [x] |
| 2 | 瘦 `infra/vector_store`，RRF/门面迁出 | [x] |
| 3 | `integrations` canonical、`multi_kb`、`pipeline/ingest` | [x] |
| 4 | 全仓库 `app.integrations` import，删 `app/ai` | [x] |
| 5 | 删除 `app/ai_stack` 目录 | [x] |

---

## 验收（已通过）

```bash
cd backend
pytest -q                    # 72 passed
grep -r 'app\.ai_stack\|app/ai_stack\|from app\.ai' app tests || echo OK
test ! -d app/ai_stack && test ! -d app/ai && echo OK
```

---

## 可选后续

| 项 | 说明 |
|----|------|
| `embedding_resolve` 边界 | 评估是否从 `tenant.models` 抽到 `integrations` |
| `technical-design.md` 全文扫尾 | 与仓库目录图完全一致 |
| Parse P0 | MinerU/插件化在 `rag/parse/backends/` 独立立项 |
