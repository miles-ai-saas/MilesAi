"""
分片阶段与入库管道之间的数据结构。

``TextChunk`` 由 ``chunk.splitter`` 产出，``pipeline.ingest`` 写入 PG 并传给向量库 metadata。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """单条分片文本；page_no 为 1-based，来自 parser metadata（pypdf/docling）。"""

    content: str  # 分片正文
    page_no: int | None = None  # 来源页码（1-based，可选）
