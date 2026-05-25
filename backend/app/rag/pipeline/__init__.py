"""
RAG 入库管道（L2）对外导出。

唯一入口 ``run_ingest_pipeline``，由 ``tenant.kb.services.ingest.run_ingest`` 在 Celery Worker 内调用。
状态机（PENDING/READY/失败）不在本包，见 ``tenant.kb.services.ingest``。
"""

from app.rag.pipeline.ingest import IngestInput, IngestResult, run_ingest_pipeline

__all__ = ["IngestInput", "IngestResult", "run_ingest_pipeline"]
