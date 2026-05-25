"""分片结果（含页码，供入库与向量索引）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """分片后单条文本；page_no 来自 pypdf/docling metadata。"""

    content: str
    page_no: int | None = None
