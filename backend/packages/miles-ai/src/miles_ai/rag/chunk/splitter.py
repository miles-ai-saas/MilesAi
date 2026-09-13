"""文本分片：RecursiveCharacter / Markdown 标题 / LangChain Document 路由。

按 metadata.parser 选择策略：docling→标题+长度；pypdf 多页→按页再切；其余→合并后 RecursiveCharacter。
chunk_size/overlap 为字符数（非 token），与 KB 创建时配置一致。
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from miles_ai.rag.chunk.types import TextChunk
from miles_core.config import get_settings

_MARKDOWN_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def _resolve_chunk_params(
    chunk_size: int | None,
    overlap: int | None,
) -> tuple[int, int]:
    """KB 未传参时使用全局默认 chunk_size / chunk_overlap。"""
    settings = get_settings()
    size = chunk_size if chunk_size is not None else settings.default_chunk_size
    ov = overlap if overlap is not None else settings.default_chunk_overlap
    return size, ov


def page_no_from_metadata(meta: dict | None) -> int | None:
    """从 LangChain metadata 解析 1-based 页码（pypdf/docling 使用 0-based `page`）。"""
    if not meta:
        return None
    for key in ("page_no", "page_number"):
        if key in meta and meta[key] is not None:
            value = int(meta[key])
            return value if value > 0 else None
    if "page" in meta and meta["page"] is not None:
        return int(meta["page"]) + 1
    return None


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """纯文本 RecursiveCharacter 分片（无 Document 元数据）。"""
    text = (text or "").strip()
    if not text:
        return []
    size, ov = _resolve_chunk_params(chunk_size, overlap)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=ov,
        length_function=len,
    )
    return splitter.split_text(text)


def _recursive_split_document(
    doc: Document,
    *,
    chunk_size: int,
    overlap: int,
) -> list[Document]:
    """单 Document 按字符长度递归切分。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
    )
    return splitter.split_documents([doc])


def _chunk_markdown_document(
    doc: Document,
    *,
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    """Docling Markdown：先按标题切，超长块再 RecursiveCharacter。"""
    page_no = page_no_from_metadata(doc.metadata)
    markdown = (doc.page_content or "").strip()
    if not markdown:
        return []

    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_MARKDOWN_HEADERS,
        strip_headers=False,
    )
    header_docs = md_splitter.split_text(markdown)
    if not header_docs:
        header_docs = [Document(page_content=markdown, metadata=dict(doc.metadata or {}))]

    pieces: list[TextChunk] = []
    for header_doc in header_docs:
        meta = dict(header_doc.metadata or {})
        if page_no is not None and "page" not in meta and "page_no" not in meta:
            meta["page"] = page_no - 1
        header_doc.metadata = meta
        sub_docs = _recursive_split_document(header_doc, chunk_size=chunk_size, overlap=overlap) if len(header_doc.page_content) > chunk_size else [header_doc]
        for sub in sub_docs:
            content = (sub.page_content or "").strip()
            if not content:
                continue
            pieces.append(
                TextChunk(
                    content=content,
                    page_no=page_no_from_metadata(sub.metadata) or page_no,
                )
            )
    return pieces


def chunk_documents(
    docs: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    """
    将 Parse 输出的 Document 列表分片为 ``TextChunk``（入库管道下一步 embed）。

    策略分支（见 metadata.parser）：
    - docling：Markdown 先按 #/##/### 标题切，超长再 RecursiveCharacter
    - pypdf 多页：每页单独切，保留 page_no
    - 其他：合并全文后 RecursiveCharacter（单页或纯文本）
    """
    if not docs:
        return []

    size, ov = _resolve_chunk_params(chunk_size, overlap)
    non_empty = [d for d in docs if (d.page_content or "").strip()]
    if not non_empty:
        return []

    parser = (non_empty[0].metadata or {}).get("parser")
    # Docling 每页/每段常为 Markdown，先保留标题边界再限制长度
    if parser == "docling":
        pieces: list[TextChunk] = []
        for doc in non_empty:
            pieces.extend(_chunk_markdown_document(doc, chunk_size=size, overlap=ov))
        return pieces

    # PyPDFLoader 一页一个 Document，避免跨页拼接后再切导致页码丢失
    if len(non_empty) > 1 and all((d.metadata or {}).get("parser") == "pypdf" for d in non_empty):
        pieces = []
        for doc in non_empty:
            page_no = page_no_from_metadata(doc.metadata)
            for text in split_text(doc.page_content, size, ov):
                pieces.append(TextChunk(content=text, page_no=page_no))
        return pieces

    combined = "\n\n".join((d.page_content or "").strip() for d in non_empty)
    page_no = page_no_from_metadata(non_empty[0].metadata) if len(non_empty) == 1 else None
    return [TextChunk(content=text, page_no=page_no) for text in split_text(combined, size, ov)]
