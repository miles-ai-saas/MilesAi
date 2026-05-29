"""rag.chunk 分片与 page_no。"""

from langchain_core.documents import Document

from app.rag.chunk.splitter import (
    chunk_documents,
    page_no_from_metadata,
    split_text,
)
from app.rag.parse.backends.docling import (
    PAGE_BREAK_PLACEHOLDER,
    markdown_pages_to_documents,
)


def test_page_no_from_metadata_zero_based_page():
    assert page_no_from_metadata({"page": 0}) == 1
    assert page_no_from_metadata({"page_no": 3}) == 3


def test_split_markdown_by_headers():
    md = "# Title\n\nintro\n\n## Section\n\nbody text here."
    docs = [
        Document(
            page_content=md,
            metadata={"parser": "docling", "page": 0},
        )
    ]
    chunks = chunk_documents(docs, chunk_size=200, overlap=0)
    assert len(chunks) >= 2
    assert any("Title" in c.content or "intro" in c.content for c in chunks)
    assert all(c.page_no == 1 for c in chunks)


def test_pypdf_multi_page_preserves_page_no():
    docs = [
        Document(page_content="page one " * 30, metadata={"parser": "pypdf", "page": 0}),
        Document(page_content="page two " * 30, metadata={"parser": "pypdf", "page": 1}),
    ]
    chunks = chunk_documents(docs, chunk_size=40, overlap=0)
    pages = {c.page_no for c in chunks}
    assert 1 in pages
    assert 2 in pages


def test_markdown_pages_to_documents_splits_placeholder():
    md = f"page1{PAGE_BREAK_PLACEHOLDER}page2"
    docs = markdown_pages_to_documents(md, filename="f.pdf")
    assert len(docs) == 2
    assert docs[0].metadata["page"] == 0
    assert docs[1].metadata["page"] == 1
    assert page_no_from_metadata(docs[1].metadata) == 2


def test_plain_text_split_unchanged():
    text = "hello " * 50
    parts = split_text(text, chunk_size=30, overlap=5)
    assert len(parts) >= 2
