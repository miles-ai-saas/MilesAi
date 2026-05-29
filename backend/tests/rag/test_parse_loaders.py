"""rag.parse 后端路由。"""

from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from app.common.exceptions import BadRequestError
from app.core.config import get_settings
from app.rag.parse.loaders import documents_to_plain_text, load_documents_from_bytes


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_load_txt_unchanged(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    data = "你好，世界".encode("utf-8")
    docs = load_documents_from_bytes(data, "a.txt", "text/plain")
    assert len(docs) == 1
    assert "你好" in docs[0].page_content
    assert docs[0].metadata.get("parser") == "text"


def test_pdf_uses_pypdf_by_default(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    fake_docs = [Document(page_content="page1", metadata={})]

    with patch(
        "app.rag.parse.loaders.load_pdf_documents",
        return_value=fake_docs,
    ) as mock_pypdf:
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")

    mock_pypdf.assert_called_once()
    assert docs[0].metadata.get("parser") == "pypdf"


def test_pdf_uses_docling_when_configured(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "docling")
    fake_docs = [Document(page_content="# Title\n\nbody", metadata={"parser": "docling"})]

    with (
        patch("app.rag.parse.loaders.docling_available", return_value=True),
        patch(
            "app.rag.parse.loaders.load_documents_with_docling",
            return_value=fake_docs,
        ) as mock_docling,
    ):
        docs = load_documents_from_bytes(b"binary", "f.pdf", "application/pdf")

    mock_docling.assert_called_once()
    assert docs[0].page_content.startswith("# Title")


def test_docling_failure_falls_back_to_pypdf(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "docling")
    monkeypatch.setenv("PARSE_DOCLING_FALLBACK_PYPDF", "true")
    fake_pypdf = [Document(page_content="fallback", metadata={})]

    with (
        patch("app.rag.parse.loaders.docling_available", return_value=True),
        patch(
            "app.rag.parse.loaders.load_documents_with_docling",
            side_effect=RuntimeError("docling boom"),
        ),
        patch(
            "app.rag.parse.loaders.load_pdf_documents",
            return_value=fake_pypdf,
        ) as mock_pypdf,
    ):
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")

    mock_pypdf.assert_called_once()
    assert docs[0].page_content == "fallback"


def test_load_image_returns_document():
    with patch("app.rag.parse.loaders.parse_image", return_value="[图片 OCR]\n\nhello"):
        docs = load_documents_from_bytes(b"\xff\xd8", "a.jpg", "image/jpeg")
    assert len(docs) == 1
    assert docs[0].metadata.get("parser") == "image"
    assert "hello" in docs[0].page_content


def test_load_audio_returns_document():
    with patch("app.rag.parse.loaders.parse_audio", return_value="[音频转写]\n\ntranscript"):
        docs = load_documents_from_bytes(b"ID3", "a.mp3", "audio/mpeg")
    assert len(docs) == 1
    assert docs[0].metadata.get("parser") == "audio"
    assert "transcript" in docs[0].page_content


def test_office_rejected_when_parse_backend_is_pypdf(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with pytest.raises(BadRequestError, match="PARSE_PDF_BACKEND"):
        load_documents_from_bytes(b"PK", "report.docx", "application/octet-stream")


def test_documents_to_plain_text_joins():
    docs = [
        Document(page_content="a"),
        Document(page_content="b"),
    ]
    assert documents_to_plain_text(docs) == "a\n\nb"
