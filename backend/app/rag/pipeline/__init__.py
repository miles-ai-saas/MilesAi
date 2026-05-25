"""RAG 入库管道对外导出（run_ingest_pipeline 由 tenant.kb.ingest 调用）。"""

from app.rag.pipeline.ingest import IngestInput, IngestResult, run_ingest_pipeline

__all__ = ["IngestInput", "IngestResult", "run_ingest_pipeline"]
