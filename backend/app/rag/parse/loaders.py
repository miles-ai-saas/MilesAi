"""LangChain Document 加载与解析后端路由。"""

from __future__ import annotations

import logging

from langchain_core.documents import Document

from app.common.exceptions import BadRequestError
from app.core.config import get_settings
from app.rag.parse.audio_parser import parse_audio
from app.rag.parse.backends.docling import DOCLING_EXTENSIONS, docling_available, load_documents_with_docling
from app.rag.parse.backends.pypdf import load_pdf_documents
from app.rag.parse.image_parser import parse_image
from app.rag.parse.media import is_audio_file, is_image_file
from app.rag.parse.text_parser import parse_text

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


def _file_ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename[filename.rfind(".") :].lower()


def _use_docling_for(ext: str, mime_type: str) -> bool:
    backend = get_settings().parse_pdf_backend.strip().lower()
    if backend != "docling":
        return False
    if ext in DOCLING_EXTENSIONS:
        return True
    if ext == ".pdf" or mime_type == "application/pdf":
        return True
    return False


def load_documents_from_bytes(
    data: bytes,
    filename: str,
    mime_type: str,
) -> list[Document]:
    """按扩展名/MIME 与配置选择解析后端。"""
    ext = _file_ext(filename)

    try:
        if is_image_file(filename, mime_type):
            text = parse_image(data, filename)
            return [
                Document(
                    page_content=text,
                    metadata={"source": filename, "parser": "image"},
                )
            ]

        if is_audio_file(filename, mime_type):
            text = parse_audio(data, filename)
            return [
                Document(
                    page_content=text,
                    metadata={"source": filename, "parser": "audio"},
                )
            ]

        if ext in _TEXT_EXTENSIONS or mime_type.startswith("text/"):
            text = parse_text(data)
            return [Document(page_content=text, metadata={"source": filename, "parser": "text"})]

        if _use_docling_for(ext, mime_type):
            if not docling_available():
                logger.warning(
                    "未安装 docling，回退 pypdf/跳过：pip install 'milesai[parse-docling]'"
                )
            else:
                try:
                    return load_documents_with_docling(data, filename, ext or ".pdf")
                except Exception as exc:
                    if not get_settings().parse_docling_fallback_pypdf:
                        raise BadRequestError(f"Docling 解析失败: {exc}") from exc
                    logger.warning(
                        "Docling 解析失败，回退 pypdf: filename=%s error=%s",
                        filename,
                        exc,
                    )

        if ext == ".pdf" or mime_type == "application/pdf":
            docs = load_pdf_documents(data, filename)
            for doc in docs:
                doc.metadata.setdefault("parser", "pypdf")
            return docs

        if _use_docling_for(ext, mime_type) and ext in DOCLING_EXTENSIONS - {".pdf"}:
            raise BadRequestError(
                f"Office/版式文件解析需要 docling：{ext}（请安装 milesai[parse-docling]）"
            )

    except BadRequestError:
        raise
    except Exception as exc:
        raise BadRequestError(f"文档解析失败: {exc}") from exc

    raise BadRequestError(f"暂不支持该文件类型: {mime_type or ext}")


def documents_to_plain_text(docs: list[Document]) -> str:
    """合并 Document 为入库用单文本。"""
    parts = [d.page_content.strip() for d in docs if (d.page_content or "").strip()]
    if not parts:
        return ""
    return "\n\n".join(parts)
