"""知识库/附件上传白名单，与 app.rag.parse.loaders 解析能力对齐。

Office（docx/pptx/xlsx/html）允许上传；实际解析需 PARSE_PDF_BACKEND=docling 且安装 parse-docling。
"""

from __future__ import annotations

from app.rag.parse.media import file_extension, is_audio_file, is_image_file

_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
OFFICE_EXTENSIONS = frozenset({".docx", ".pptx", ".xlsx", ".html", ".htm"})

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
    }
)

KB_ALLOWED_EXTENSIONS = (
    _TEXT_EXTENSIONS
    | {".pdf"}
    | OFFICE_EXTENSIONS
    | {".jpg", ".jpeg", ".png", ".webp", ".mp3", ".wav", ".m4a", ".ogg", ".webm"}
)


def is_kb_upload_allowed(filename: str, mime: str) -> bool:
    ext = file_extension(filename)
    if mime in KB_ALLOWED_MIMES or ext in KB_ALLOWED_EXTENSIONS:
        return True
    return is_image_file(filename, mime) or is_audio_file(filename, mime)


def kb_upload_accept_attribute() -> str:
    """HTML input accept 属性，与 KB_ALLOWED_EXTENSIONS 一致。"""
    return ",".join(sorted(e for e in KB_ALLOWED_EXTENSIONS if e.startswith(".")))


def kb_upload_allowed_hint() -> str:
    return (
        "支持 TXT/MD/PDF、Office（DOCX/PPTX/XLSX/HTML，解析需 docling）、"
        "图片（JPG/PNG/WebP）、音频（MP3/WAV 等）"
    )
