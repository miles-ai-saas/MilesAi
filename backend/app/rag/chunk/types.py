"""分片结果（含页码，供入库与向量索引）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    content: str
    # 写入 kb_document_chunks.page_no 与向量库 metadata，供引用展示
    page_no: int | None = None
