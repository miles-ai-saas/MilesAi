"""
知识库 L1 用例：CRUD、上传、检索、删除编排。

目录职责
--------
- ``service.py``：``KnowledgeBaseService`` 门面（仓库注入 + Mixin 组合）。
- ``core.py``：KB CRUD、配额、检索日志。
- ``documents.py``：文档上传/列表/删除与 Celery ingest。
- ``search.py``：文本/视觉/混合检索。

上传（异步）
------------
校验配额/类型 → 写 OSS → 建 ``Document(PENDING)`` → ``ingest_document.delay``
→ Worker ``run_ingest`` → ``rag.pipeline``（详见各层模块注释）。

检索（同步 HTTP）
-----------------
``embed_query_for_kb`` → ``search_kb_chunks`` → 从 PG 取 **完整** chunk.content 组装响应
（向量库 hit 仅含 content_preview 截断）。

删除
----
``clear_document_derived_data_async``（PG 分片 + vector_ref + 向量库）→ 删 OSS → 软删文档。

约束
----
``embedding_model_config_id`` / ``embedding_dimension`` 在 **创建 KB 时固化**，后续不可改。

对外::

    from app.tenant.kb.services.kb import KnowledgeBaseService
"""

from app.tenant.kb.services.kb.service import KnowledgeBaseService

__all__ = ["KnowledgeBaseService"]
