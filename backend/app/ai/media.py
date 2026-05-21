"""多模态文件类型判定。"""

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
    if "." not in filename:
        return ""
    return filename[filename.rfind(".") :].lower()


def is_image_file(filename: str, mime_type: str) -> bool:
    ext = file_extension(filename)
    return mime_type in _IMAGE_MIMES or ext in _IMAGE_EXTENSIONS


def is_audio_file(filename: str, mime_type: str) -> bool:
    ext = file_extension(filename)
    return mime_type in _AUDIO_MIMES or ext in _AUDIO_EXTENSIONS


def vector_type_for_document(filename: str, mime_type: str) -> str:
    if is_image_file(filename, mime_type):
        return "image"
    if is_audio_file(filename, mime_type):
        return "audio"
    return "text"
