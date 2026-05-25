"""
RAG 领域能力（L2）：Parse → Chunk → Index → Retrieve → Generate。

子包一览
--------
- ``parse``：多格式解析为 LangChain Document
- ``chunk``：分片策略（RecursiveCharacter / Markdown / 按页）
- ``index.gateway``：向量库读写门面（勿直连接 infra.vector_store）
- ``pipeline.ingest``：入库管道（embed 在此，向量库用预计算向量）
- ``retrieve``：单库/多库检索、hybrid RRF、rerank
- ``generate``：拼装上下文与生成回答

架构说明：docs/architecture/layering.md、docs/guides/knowledge-base.md
"""
