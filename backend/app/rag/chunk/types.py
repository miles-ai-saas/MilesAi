"""分片结果（含页码，供入库与向量索引）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    content: str
    page_no: int | None = None
