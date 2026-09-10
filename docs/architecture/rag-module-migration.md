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
pytest -q
grep -r 'app\.ai_stack\|app/ai_stack\|from app\.ai' app tests || echo OK
test ! -d app/ai_stack && test ! -d app/ai && echo OK
```

---

## 迁移后增量（文档与代码对齐）

| 项 | 说明 |
|----|------|
| 入库管道 | `rag/pipeline/ingest.py`：`load_documents_from_bytes` → `chunk_documents` |
| Parse | `backends/pypdf`、`backends/docling`（`[parse-docling]`）、图/音接入 loaders |
| Chunk | `chunk_documents`、`TextChunk.page_no`；Docling Markdown 标题分片 |
| 检索 | `rag/retrieve/*`；`integrations.langchain.vectorstores` 调 `multi_kb` |
| 文档 | [layering.md](./layering.md)、[knowledge-base.md](../guides/knowledge-base.md)、[ai-stack.md](../guides/ai-stack.md) |

---

## 可选后续

| 项 | 说明 |
|----|------|
| `embedding_resolve` 边界 | 评估是否从 `tenant.models` 抽到 `integrations` |
| Parse 插件 | PaddleOCR 等仅增 `rag/parse/backends/*`，不含 MinerU/RAG-Anything |

> **已闭环（2026-09-10）**：上传白名单与解析能力对齐——图/音/视频的扩展名与 MIME 改由
> [parse/media.py](../../backend/app/rag/parse/media.py) 单一来源导出、`upload_policy` 复用；
> `OFFICE_EXTENSIONS ⊆ DOCLING_EXTENSIONS`、media 判定 ⊆ 白名单、白名单扩展名/MIME 往返可接受、
> 前端 `accept` 全覆盖等不变式由 `tests/rag/test_upload_policy_alignment.py` 守卫。Docling 可读但
> 白名单刻意不收的 TIFF/BMP 归「允许上传 ≠ 一定能解析」边界，保持现状（见 `upload_policy` 模块注释）。
