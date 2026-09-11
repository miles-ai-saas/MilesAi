"""分片：解析后的 Document → TextChunk（供 pipeline 向量化）。"""

from miles_ai.rag.chunk.splitter import chunk_documents, page_no_from_metadata, split_text
from miles_ai.rag.chunk.types import TextChunk

__all__ = ["TextChunk", "chunk_documents", "page_no_from_metadata", "split_text"]
