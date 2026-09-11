# RAG 知识库

**状态：** 已实现  
**PRD 对照：** 模块6 RAG多模态知识库  
**架构：** [layering.md](../architecture/layering.md) · [knowledge-base.md](../guides/knowledge-base.md)

---

## 1. 背景与目标

租户 **知识库** 管理文档上传、异步入库（parse → chunk → embed → index）、向量/hybrid 检索。向量化规格在 **创建 KB 时固化**（维度、embedding 模型）；文件存 MinIO，向量存 Weaviate/Milvus。

### 1.1 交付范围

- KB CRUD、配额查询、embedding profiles 目录
- 文档上传 → Celery `ingest_document`（含 **视频** MP4/MOV/WebM）
- 文档状态机、分片列表、重试、删除（级联向量/OSS）
- `POST …/search` vector / hybrid + **`media_types` 过滤** + **`query_document_id` 以图/视频搜（OCR MVP）** + **`visual_search` CLIP 视觉相似度**
- 检索日志 `kb_search_logs`
- 前端：`/workbench/kb`、`/workbench/kb/[id]`

### 1.2 明确不做

- PaddleOCR / 高精度 OCR 插件（按需，见 [backlog.md](../product/backlog.md)）

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `kb_bases` | embedding 维度、chunk、retrieval_mode、hybrid_alpha、rerank、**visual_embedding_model_config_id（CLIP）** |
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
POST /kb/{id}/search             # SearchRequest: query, top_k, mode, visual_search…
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
    → embed_texts_for_kb（文本）或 CLIP 图片向量（配置了 visual 模型时）
    → upsert_chunk_vector
    → PG chunks + vector_refs
    → status READY
```

入口 L1：`tenant.kb.services.ingest`；L2：`miles_ai.rag.pipeline.run_ingest_pipeline`。

---

## 5. 检索流水线

```
POST /search
    → visual_search ? CLIP embed(query|参考图) : embed_query_for_kb（含 OCR MVP）
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
| `embedding_profile` | 创建 KB 时选择，如 `local-bge-zh`(768)、`dashscope-v3`(1024)；可选 `clip-vit-b-32`(512) 作视觉模型 |
| `PARSE_PDF_BACKEND` | `pypdf` \| `docling` |
| `[parse-docling]` / `[multimodal]` | 可选依赖 |

---

## 7. 前端

```
ui/workbench/app/workbench/kb/page.tsx
ui/workbench/app/workbench/kb/[id]/page.tsx
```

---

## 8. 后端文件清单

```
backend/packages/miles-core/src/miles_core/models/kb/knowledge_base.py
backend/packages/miles-portal/src/miles_portal/tenant/kb/
backend/packages/miles-ai/src/miles_ai/rag/{parse,chunk,index,retrieve,generate,pipeline}/
backend/packages/miles-worker/src/miles_worker/tasks/ingest.py
backend/packages/miles-portal/src/miles_portal/deletion/cascade.py   # 删 KB 级联
```

---

## 9. 测试计划

1. 创建 KB 选 profile → 上传 txt → task + READY
2. search 返回 hits + score；hybrid 与 vector 模式切换
3. 删 document → 向量与 OSS 清理
5. 配置 CLIP 视觉模型 → 上传图片 → visual_search 以图搜图 / 文本搜图

---

## 10. 参考

- [knowledge-base.md](../guides/knowledge-base.md) — 主文档
- [task-center.md](./task-center.md) — ingest 任务
- [vector-database-selection.md](../architecture/vector-database-selection.md)
