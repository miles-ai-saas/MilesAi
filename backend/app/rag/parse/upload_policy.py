"""
知识库/附件上传白名单，与 ``parse.loaders`` 解析能力对齐。

允许上传 ≠ 一定能解析：Office 允许进库，但解析需 ``PARSE_PDF_BACKEND=docling`` 且 Worker 安装 parse-docling。
前端 ``accept`` / 失败提示由本模块统一生成，避免与后端路由不一致。
"""

from __future__ import annotations

from app.rag.parse.media import file_extension, is_audio_file, is_image_file, is_video_file

_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
OFFICE_EXTENSIONS = frozenset({".docx", ".pptx", ".xlsx", ".html", ".htm"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv"})

KB_ALLOWED_MIMES = frozenset(
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
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/webm",
        "audio/ogg",
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "video/x-matroska",
    }
)

KB_ALLOWED_EXTENSIONS = (
    _TEXT_EXTENSIONS | {".pdf"} | OFFICE_EXTENSIONS | {".jpg", ".jpeg", ".png", ".webp", ".mp3", ".wav", ".m4a", ".ogg", ".webm"} | VIDEO_EXTENSIONS
)


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
