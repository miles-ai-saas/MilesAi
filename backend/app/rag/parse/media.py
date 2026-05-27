"""
多模态文件类型判定。

用于 loaders 路由（image/audio）与 ``vector_type_for_document``（写入 VectorRef.vector_type）。
"""

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

_VIDEO_MIMES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


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


def is_video_file(filename: str, mime_type: str) -> bool:
    """是否按视频解析（抽帧 + 音轨转写）。"""
    ext = file_extension(filename)
    return mime_type in _VIDEO_MIMES or ext in _VIDEO_EXTENSIONS


def vector_type_for_document(filename: str, mime_type: str) -> str:
    """写入 kb_vector_refs.vector_type，区分文本/图/音/视频入库来源。"""
    if is_image_file(filename, mime_type):
        return "image"
    if is_audio_file(filename, mime_type):
        return "audio"
    if is_video_file(filename, mime_type):
        return "video"
    return "text"
