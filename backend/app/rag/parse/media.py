"""多模态文件类型判定（图片/音频路由与 vector_type）。"""

_IMAGE_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_AUDIO_MIMES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


def file_extension(filename: str) -> str:
    """小写扩展名（含点）。"""
    if "." not in filename:
        return ""
    return filename[filename.rfind(".") :].lower()


def is_image_file(filename: str, mime_type: str) -> bool:
    """是否按图片解析（OCR 或占位文本）。"""
    ext = file_extension(filename)
    return mime_type in _IMAGE_MIMES or ext in _IMAGE_EXTENSIONS


def is_audio_file(filename: str, mime_type: str) -> bool:
    """是否按音频解析（Whisper 或占位文本）。"""
    ext = file_extension(filename)
    return mime_type in _AUDIO_MIMES or ext in _AUDIO_EXTENSIONS


def vector_type_for_document(filename: str, mime_type: str) -> str:
    """写入 kb_vector_refs.vector_type，区分文本/图/音入库来源。"""
    if is_image_file(filename, mime_type):
        return "image"
    if is_audio_file(filename, mime_type):
        return "audio"
    return "text"
