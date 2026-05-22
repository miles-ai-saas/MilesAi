"""PDF 解析：LangChain PyPDFLoader（轻量兜底）。"""

from __future__ import annotations

import os
import tempfile

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader


def load_pdf_documents(data: bytes, filename: str) -> list[Document]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        docs = PyPDFLoader(tmp_path).load()
        for i, doc in enumerate(docs):
            doc.metadata["source"] = filename
            # page 为 0-based；入库时由 chunk.page_no_from_metadata 转为 1-based
            doc.metadata.setdefault("page", i)
        return docs
    finally:
        os.unlink(tmp_path)
