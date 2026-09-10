"""
知识库/附件上传白名单，与 ``parse.loaders`` 解析能力对齐。

允许上传 ≠ 一定能解析：Office 允许进库，但解析需 ``PARSE_PDF_BACKEND=docling`` 且 Worker
安装 parse-docling。Docling 本身还能读 TIFF/BMP（见 ``backends.docling.DOCLING_EXTENSIONS``），
但白名单**刻意不收**——``parse_image`` 只认 JPG/PNG/WebP，收了会变成「可上传但必解析失败」的坑。

图/音/视频的扩展名与 MIME 复用 ``parse.media`` 单一来源（避免白名单与 ``is_*_file`` 判定漂移）；
Office 扩展名 ⊆ ``DOCLING_EXTENSIONS`` 由 ``tests/rag/test_upload_policy_alignment.py`` 守卫。
前端 ``accept`` / 失败提示由本模块统一生成，避免与后端路由不一致。
"""

from __future__ import annotations

from app.rag.parse.media import (
    AUDIO_EXTENSIONS,
    AUDIO_MIMES,
    IMAGE_EXTENSIONS,
    IMAGE_MIMES,
    VIDEO_EXTENSIONS,
    VIDEO_MIMES,
    file_extension,
    is_audio_file,
    is_image_file,
    is_video_file,
)

_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
PDF_EXTENSIONS = frozenset({".pdf"})
OFFICE_EXTENSIONS = frozenset({".docx", ".pptx", ".xlsx", ".html", ".htm"})

_STRUCTURED_MIMES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
        "application/xhtml+xml",
    }
)

KB_ALLOWED_MIMES = _STRUCTURED_MIMES | IMAGE_MIMES | AUDIO_MIMES | VIDEO_MIMES

KB_ALLOWED_EXTENSIONS = _TEXT_EXTENSIONS | PDF_EXTENSIONS | OFFICE_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def is_kb_upload_allowed(filename: str, mime: str) -> bool:
    """校验扩展名/MIME 是否在 KB 白名单内。"""
    ext = file_extension(filename)
    if mime in KB_ALLOWED_MIMES or ext in KB_ALLOWED_EXTENSIONS:
        return True
    return is_image_file(filename, mime) or is_audio_file(filename, mime) or is_video_file(filename, mime)


def kb_upload_accept_attribute() -> str:
    """HTML input accept 属性，与 KB_ALLOWED_EXTENSIONS 一致。"""
    return ",".join(sorted(e for e in KB_ALLOWED_EXTENSIONS if e.startswith(".")))


def kb_upload_allowed_hint() -> str:
    """上传失败时返回给前端的友好提示文案。"""
    return "支持 TXT/MD/PDF、Office（DOCX/PPTX/XLSX/HTML，解析需 docling）、图片（JPG/PNG/WebP）、音频（MP3/WAV 等）、视频（MP4/MOV/WebM，需 ffmpeg）"
