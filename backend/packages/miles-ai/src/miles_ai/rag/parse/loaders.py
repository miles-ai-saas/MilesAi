"""
LangChain Document 加载与解析后端路由。

入库唯一 Parse 入口
------------------
``load_documents_from_bytes`` ← ``pipeline.run_ingest_pipeline`` ← Celery/上传。

路由顺序（自上而下命中即返回）
----------------------------
1. 图片 / 音频 / 视频 → ``parse_image`` / ``parse_audio`` / ``parse_video``
2. 纯文本 .txt/.md 或 text/* → ``parse_text``
3. Docling（``PARSE_PDF_BACKEND=docling`` 且扩展名支持）→ 失败可 ``parse_docling_fallback_pypdf`` 回退
4. PDF → ``load_pdf_documents``（PyPDFLoader，按页 Document）
5. Office 等 → 必须 docling；未配置则 ``BadRequestError`` 提示安装 parse-docling

输出 metadata.parser 供 ``chunk.chunk_documents`` 选择分片策略（docling/pypdf/...）。
"""

from __future__ import annotations

from langchain_core.documents import Document

from miles_ai.rag.parse.audio_parser import parse_audio
from miles_ai.rag.parse.backends.docling import DOCLING_EXTENSIONS, docling_available, load_documents_with_docling
from miles_ai.rag.parse.backends.pypdf import load_pdf_documents
from miles_ai.rag.parse.image_parser import parse_image
from miles_ai.rag.parse.media import VIDEO_EXTENSIONS, is_audio_file, is_image_file
from miles_ai.rag.parse.text_parser import parse_text
from miles_ai.rag.parse.upload_policy import OFFICE_EXTENSIONS
from miles_ai.rag.parse.video_parser import parse_video
from miles_common.exceptions import BadRequestError
from miles_core.config import get_settings
from miles_core.logging import get_logger

logger = get_logger(__name__)

_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


def _raise_if_office_unparseable(ext: str) -> None:
    """Office 仅 docling 路径；pypdf 默认或缺依赖时给出可操作的 fail_reason 文案。"""
    if ext not in OFFICE_EXTENSIONS:
        return
    backend = get_settings().parse_pdf_backend.strip().lower()
    if backend != "docling":
        raise BadRequestError(
            "Office 文档解析需将 PARSE_PDF_BACKEND 设为 docling（当前为 pypdf）；API 与 Celery Worker 均需安装：pip install 'milesai[parse-docling]'"
        )
    if not docling_available():
        raise BadRequestError(f"Office 文档解析需要 docling（{ext}），请在 Worker 执行：pip install 'milesai[parse-docling]'")


def _file_ext(filename: str) -> str:
    """提取小写扩展名（含点）。"""
    if "." not in filename:
        return ""
    return filename[filename.rfind(".") :].lower()


def _use_docling_for(ext: str, mime_type: str) -> bool:
    """是否尝试 Docling；由 PARSE_PDF_BACKEND=docling 与扩展名共同决定。"""
    backend = get_settings().parse_pdf_backend.strip().lower()
    if backend != "docling":
        return False
    if ext in DOCLING_EXTENSIONS:
        return True
    if ext == ".pdf" or mime_type == "application/pdf":
        return True
    return False


def _single_doc(text: str, filename: str, parser: str) -> list[Document]:
    """单段文本 → 单个 Document；``metadata.parser`` 供 chunk 阶段选分片策略。"""
    return [Document(page_content=text, metadata={"source": filename, "parser": parser})]


def _try_docling(data: bytes, filename: str, ext: str, mime_type: str) -> list[Document] | None:
    """Docling 可用时尝试解析；未启用、未安装或已按配置回退时返回 None 交给后续分支。"""
    if not _use_docling_for(ext, mime_type):
        return None
    if not docling_available():
        logger.warning("未安装 docling，回退 pypdf/跳过：pip install 'milesai[parse-docling]'")
        return None
    try:
        return load_documents_with_docling(data, filename, ext or ".pdf")
    except Exception as exc:
        if not get_settings().parse_docling_fallback_pypdf:
            raise BadRequestError(f"Docling 解析失败: {exc}") from exc
        logger.warning("Docling 解析失败，回退 pypdf: filename=%s error=%s", filename, exc)
        return None


def load_documents_from_bytes(
    data: bytes,
    filename: str,
    mime_type: str,
) -> list[Document]:
    """按扩展名/MIME 与配置选择解析后端。"""
    ext = _file_ext(filename)

    try:
        # 多模态：无 OCR/Whisper/ffmpeg 时 parse_* 仍返回占位文本，保证流程可走完。
        # 视频判定与 media.VIDEO_EXTENSIONS 同源（.webm 归视频）；显式 audio/* mime
        # 的例外留给音频分支，与 vector_type_for_document 的判定保持一致。
        if mime_type.startswith("video/") or (ext in VIDEO_EXTENSIONS and not mime_type.startswith("audio/")):
            return _single_doc(parse_video(data, filename), filename, "video")

        if is_image_file(filename, mime_type):
            return _single_doc(parse_image(data, filename), filename, "image")

        if is_audio_file(filename, mime_type):
            return _single_doc(parse_audio(data, filename), filename, "audio")

        if ext in _TEXT_EXTENSIONS or mime_type.startswith("text/"):
            return _single_doc(parse_text(data), filename, "text")

        docs = _try_docling(data, filename, ext, mime_type)
        if docs is not None:
            return docs

        if ext == ".pdf" or mime_type == "application/pdf":
            docs = load_pdf_documents(data, filename)
            for doc in docs:
                doc.metadata.setdefault("parser", "pypdf")
            return docs

        _raise_if_office_unparseable(ext)

    except BadRequestError:
        raise
    except Exception as exc:
        raise BadRequestError(f"文档解析失败: {exc}") from exc

    _raise_if_office_unparseable(ext)
    raise BadRequestError(f"暂不支持该文件类型: {mime_type or ext}")


def documents_to_plain_text(docs: list[Document]) -> str:
    """合并多页 Document 为单字符串（调试或简易路径；pipeline 用 chunk_documents）。"""
    parts = [d.page_content.strip() for d in docs if (d.page_content or "").strip()]
    if not parts:
        return ""
    return "\n\n".join(parts)
