"""rag.parse 后端路由。"""

from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from miles_ai.rag.parse.loaders import documents_to_plain_text, load_documents_from_bytes
from miles_common.exceptions import BadRequestError
from miles_core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_load_txt_unchanged(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    data = "你好，世界".encode()
    docs = load_documents_from_bytes(data, "a.txt", "text/plain")
    assert len(docs) == 1
    assert "你好" in docs[0].page_content
    assert docs[0].metadata.get("parser") == "text"


def test_pdf_uses_pypdf_by_default(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    fake_docs = [Document(page_content="page1", metadata={})]

    with patch(
        "miles_ai.rag.parse.loaders.load_pdf_documents",
        return_value=fake_docs,
    ) as mock_pypdf:
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")

    mock_pypdf.assert_called_once()
    assert docs[0].metadata.get("parser") == "pypdf"


def test_pdf_uses_docling_when_configured(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "docling")
    fake_docs = [Document(page_content="# Title\n\nbody", metadata={"parser": "docling"})]

    with (
        patch("miles_ai.rag.parse.loaders.docling_available", return_value=True),
        patch(
            "miles_ai.rag.parse.loaders.load_documents_with_docling",
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
        patch("miles_ai.rag.parse.loaders.docling_available", return_value=True),
        patch(
            "miles_ai.rag.parse.loaders.load_documents_with_docling",
            side_effect=RuntimeError("docling boom"),
        ),
        patch(
            "miles_ai.rag.parse.loaders.load_pdf_documents",
            return_value=fake_pypdf,
        ) as mock_pypdf,
    ):
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")

    mock_pypdf.assert_called_once()
    assert docs[0].page_content == "fallback"


def test_load_image_returns_document():
    with patch("miles_ai.rag.parse.loaders.parse_image", return_value="[图片 OCR]\n\nhello"):
        docs = load_documents_from_bytes(b"\xff\xd8", "a.jpg", "image/jpeg")
    assert len(docs) == 1
    assert docs[0].metadata.get("parser") == "image"
    assert "hello" in docs[0].page_content


def test_load_audio_returns_document():
    with patch("miles_ai.rag.parse.loaders.parse_audio", return_value="[音频转写]\n\ntranscript"):
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


# --------------------------------------------------------------------------- #
# 视频路由（含与 media 判定不一致之处）
# --------------------------------------------------------------------------- #


def test_load_video_by_mime_returns_document(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_video", return_value="[视频关键帧]\n\nframes"):
        docs = load_documents_from_bytes(b"\x00\x00", "a.mp4", "video/mp4")
    assert len(docs) == 1
    assert docs[0].metadata.get("parser") == "video"
    assert "frames" in docs[0].page_content


def test_load_video_by_extension_without_video_mime(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_video", return_value="v") as mock_video:
        docs = load_documents_from_bytes(b"\x00", "a.mkv", "application/octet-stream")
    mock_video.assert_called_once()
    assert docs[0].metadata.get("parser") == "video"


def test_any_video_mime_prefix_routes_to_video(monkeypatch):
    """路由按 ``startswith("video/")`` 判定，比 ``media.VIDEO_MIMES`` 白名单更宽。"""
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_video", return_value="v"):
        docs = load_documents_from_bytes(b"\x00", "clip.bin", "video/x-msvideo")
    assert docs[0].metadata.get("parser") == "video"


# 以下两项固化「loaders 路由」与「media.VIDEO_EXTENSIONS / is_video_file」的差异：
# .webm 同时是 media 的音频与视频扩展名，而本路由的视频扩展名集合不含 .webm，
# 故无 video/* mime 时落到音频分支。统一语义需先确认 .webm 的入库类型，故先锁现状。


def test_webm_without_video_mime_routes_to_audio(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_audio", return_value="a") as mock_audio:
        docs = load_documents_from_bytes(b"\x00", "a.webm", "application/octet-stream")
    mock_audio.assert_called_once()
    assert docs[0].metadata.get("parser") == "audio"


def test_mp4_with_audio_mime_is_unsupported(monkeypatch):
    """视频分支要求 mime 非 audio/*，而 audio/mp4 不在音频白名单，故当前不被接受。"""
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with pytest.raises(BadRequestError, match="暂不支持该文件类型"):
        load_documents_from_bytes(b"\x00", "a.mp4", "audio/mp4")


# --------------------------------------------------------------------------- #
# Docling 回退与失败
# --------------------------------------------------------------------------- #


def test_docling_unavailable_falls_back_to_pypdf(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "docling")
    fake_docs = [Document(page_content="fallback", metadata={})]
    with (
        patch("miles_ai.rag.parse.loaders.docling_available", return_value=False),
        patch("miles_ai.rag.parse.loaders.load_documents_with_docling") as mock_docling,
        patch("miles_ai.rag.parse.loaders.load_pdf_documents", return_value=fake_docs) as mock_pypdf,
    ):
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")
    mock_docling.assert_not_called()
    mock_pypdf.assert_called_once()
    assert docs[0].page_content == "fallback"


def test_docling_failure_without_fallback_raises(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "docling")
    monkeypatch.setenv("PARSE_DOCLING_FALLBACK_PYPDF", "false")
    with (
        patch("miles_ai.rag.parse.loaders.docling_available", return_value=True),
        patch("miles_ai.rag.parse.loaders.load_documents_with_docling", side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(BadRequestError, match="Docling 解析失败"):
            load_documents_from_bytes(b"binary", "f.pdf", "application/pdf")


# --------------------------------------------------------------------------- #
# pypdf metadata 与异常包装
# --------------------------------------------------------------------------- #


def test_pypdf_keeps_existing_parser_metadata(monkeypatch):
    """``setdefault``：解析器已自带 parser 时不覆盖。"""
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    fake_docs = [Document(page_content="p", metadata={"parser": "custom"})]
    with patch("miles_ai.rag.parse.loaders.load_pdf_documents", return_value=fake_docs):
        docs = load_documents_from_bytes(b"%PDF", "f.pdf", "application/pdf")
    assert docs[0].metadata["parser"] == "custom"


def test_unsupported_type_raises(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with pytest.raises(BadRequestError, match="暂不支持该文件类型"):
        load_documents_from_bytes(b"\x00", "a.xyz", "application/octet-stream")


def test_parser_exception_is_wrapped(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_image", side_effect=RuntimeError("ocr boom")):
        with pytest.raises(BadRequestError, match="文档解析失败"):
            load_documents_from_bytes(b"\xff\xd8", "a.jpg", "image/jpeg")


def test_bad_request_error_passes_through_unwrapped(monkeypatch):
    monkeypatch.setenv("PARSE_PDF_BACKEND", "pypdf")
    with patch("miles_ai.rag.parse.loaders.parse_image", side_effect=BadRequestError("原始拒绝原因")):
        with pytest.raises(BadRequestError, match="原始拒绝原因"):
            load_documents_from_bytes(b"\xff\xd8", "a.jpg", "image/jpeg")
