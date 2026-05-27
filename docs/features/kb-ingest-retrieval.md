# RAG 知识库

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块6 RAG多模态知识库  
**架构：** [layering.md](../architecture/layering.md) · [knowledge-base.md](../guides/knowledge-base.md)

---

## 1. 背景与目标

租户 **知识库** 管理文档上传、异步入库（parse → chunk → embed → index）、向量/hybrid 检索。向量化规格在 **创建 KB 时固化**（维度、embedding 模型）；文件存 MinIO，向量存 Weaviate/Milvus。

### 1.1 交付范围

- KB CRUD、配额查询、embedding profiles 目录
- 文档上传 → Celery `ingest_document`
- 文档状态机、分片列表、重试、删除（级联向量/OSS）
- `POST …/search` vector / hybrid + 可选 rerank
- 检索日志 `kb_search_logs`
- 前端：`/workbench/kb`、`/workbench/kb/[id]`

### 1.2 明确不做

- 以图搜图 / 文本搜图（当前文本向量 + 关键词 hybrid）
- 视频入库解析
- PaddleOCR / 高精度 OCR 插件（按需立项；现网图：`pytesseract` `[multimodal]`，见 [backlog.md](../product/backlog.md)）
- 老格式 Office（`.doc`/`.xls`/`.ppt`；Open XML docx/pptx/xlsx 已支持上传）

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `kb_bases` | embedding 维度、chunk、retrieval_mode、hybrid_alpha、rerank |
| `kb_documents` | OSS 路径、status、celery_task_id |
| `kb_document_chunks` | 分片正文（PG） |
| `kb_vector_refs` | 外部 vector_id |
| `kb_search_logs` | 检索审计 |

**Document.status：** `pending` → `parsing` → `embedding` → `ready` | `parse_failed` | `embed_failed`

---

## 3. API

前缀：`/api/v1/kb`  
权限：`kb:read` · `kb:write` · `kb:document:upload`

```
GET  /kb/meta
GET  /kb/quota
GET  /kb/embedding-profiles
GET  /kb
POST /kb                         # body 含 embedding_profile，创建后不可改维度
GET/PATCH/DELETE /kb/{id}
GET  /kb/{id}/documents
POST /kb/{id}/documents          # multipart → PENDING + ingest delay
POST /kb/{id}/documents/{doc_id}/retry
GET  /kb/{id}/documents/{doc_id}/chunks
DELETE /kb/{id}/documents/{doc_id}
GET  /kb/{id}/search-logs
POST /kb/{id}/search             # SearchRequest: query, top_k, mode…
```

---

## 4. 入库流水线

```
upload → OSS + kb_documents (PENDING)
    → TaskService.create_record
    → ingest_document (queue: parse)
Worker:
    load_documents_from_bytes (pypdf | docling | text | image | audio)
    → chunk_documents
    → embed_texts_for_kb
    → upsert_chunk_vector
    → PG chunks + vector_refs
    → status READY
```

入口 L1：`tenant.kb.services.ingest`；L2：`app.rag.pipeline.run_ingest_pipeline`。

---

## 5. 检索流水线

```
POST /search
    → embed_query_for_kb
    → rag.retrieve.search_kb_chunks (vector | hybrid RRF)
    → 可选 rerank
    → 回填 PG chunk 正文
    → 写 kb_search_logs
```

智能体/流程：`rag_answer` / `KnowledgeSearch` 节点共用检索门面。

---

## 6. 配置要点

| 项 | 说明 |
|----|------|
| `VECTOR_STORE_BACKEND` | weaviate / milvus（部署级 L1） |
| `embedding_profile` | 创建 KB 时选择，如 `local-bge-zh`(768)、`dashscope-v3`(1024) |
| `PARSE_PDF_BACKEND` | `pypdf` \| `docling` |
| `[parse-docling]` / `[multimodal]` | 可选依赖 |

---

## 7. 前端

```
frontend/app/workbench/kb/page.tsx
frontend/app/workbench/kb/[id]/page.tsx
```

---

## 8. 后端文件清单

```
backend/app/models/kb.py
backend/app/tenant/kb/
backend/app/rag/{parse,chunk,index,retrieve,generate,pipeline}/
backend/app/workers/tasks/ingest.py
backend/app/deletion/cascade.py          # 删 KB 级联
```

---

## 9. 测试计划

1. 创建 KB 选 profile → 上传 txt → task + READY
2. search 返回 hits + score；hybrid 与 vector 模式切换
3. 删 document → 向量与 OSS 清理
4. 改 embedding 维度 → 创建后 PATCH 拒绝

---

## 10. 参考

- [knowledge-base.md](../guides/knowledge-base.md) — 主文档
- [task-center.md](./task-center.md) — ingest 任务
- [vector-database-selection.md](../architecture/vector-database-selection.md)
